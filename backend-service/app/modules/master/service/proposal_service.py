from datetime import datetime, timezone
import hashlib
import json
from typing import Any, Dict, List, Optional
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.exception.app_exceptions import BusinessException, ConflictException, NotFoundException, ValidationException
from app.core.pagination.page_result import PageResult
from app.modules.master.entity.master_message_entity import MasterMessage
from app.modules.master.entity.master_proposal_entity import MasterProposal
from app.modules.master.repository.conversation_repository import ConversationRepository
from app.modules.master.repository.message_repository import MessageRepository
from app.modules.master.repository.proposal_repository import ProposalFilter, ProposalRepository
from app.modules.master.service.proposal_executor import ProposalExecutor
from app.modules.strategies.service.conflict_analyzer import ConflictAnalyzer
from app.modules.strategies.service.definition_validator import DefinitionValidator


class ProposalConfirmRequest:
    mode: str = "ADD_AS_DRAFT"  # ADD_AS_DRAFT, ADD_AND_ACTIVATE, APPLY
    acknowledgedComplicationCodes: List[str] = []
    typedPhrase: Optional[str] = None


class ProposalService:
    """
    Manages proposal lifecycle, search, revalidation, rejection, and safe confirmation.
    """

    def __init__(
        self,
        proposal_repo: Optional[ProposalRepository] = None,
        conversation_repo: Optional[ConversationRepository] = None,
        message_repo: Optional[MessageRepository] = None,
        executor: Optional[ProposalExecutor] = None,
        validator: Optional[DefinitionValidator] = None,
        conflict_analyzer: Optional[ConflictAnalyzer] = None,
    ):
        self.proposal_repo = proposal_repo or ProposalRepository()
        self.conversation_repo = conversation_repo or ConversationRepository()
        self.message_repo = message_repo or MessageRepository()
        self.executor = executor or ProposalExecutor()
        self.validator = validator or DefinitionValidator()
        self.conflict_analyzer = conflict_analyzer or ConflictAnalyzer()

    async def get_by_id(self, session: AsyncSession, proposal_id: int) -> MasterProposal:
        proposal = await self.proposal_repo.get_by_id(session, proposal_id)
        if not proposal:
            raise NotFoundException(message=f"Proposal #{proposal_id} not found")
        return proposal

    async def search(self, session: AsyncSession, filter_obj: ProposalFilter) -> PageResult[MasterProposal]:
        return await self.proposal_repo.search(session, filter_obj)

    async def confirm(
        self,
        session: AsyncSession,
        proposal_id: int,
        mode: str = "ADD_AS_DRAFT",
        acknowledged_codes: Optional[List[str]] = None,
        typed_phrase: Optional[str] = None,
    ) -> MasterProposal:
        """
        Executes strict Section 5.3 confirm checks before mutating Strategy module.
        """
        acknowledged_codes = acknowledged_codes or []
        proposal = await self.get_by_id(session, proposal_id)

        # 1. Check status and expiration
        if proposal.proposalStatus != "PENDING":
            raise ConflictException(message=f"Proposal #{proposal_id} is already in state '{proposal.proposalStatus}'")

        now = datetime.now(timezone.utc)
        if proposal.expiresAt.replace(tzinfo=timezone.utc) <= now:
            proposal.proposalStatus = "EXPIRED"
            await self.proposal_repo.save(session, proposal)
            raise ConflictException(message=f"Proposal #{proposal_id} has expired (PROPOSAL_EXPIRED)")

        # 2. Verify content hash
        payload_str = json.dumps(proposal.payload, sort_keys=True)
        current_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        if current_hash != proposal.contentHash:
            proposal.proposalStatus = "FAILED"
            proposal.failureReason = "Content hash mismatch (payload was modified outside system)"
            await self.proposal_repo.save(session, proposal)
            raise ConflictException(message="Proposal payload hash verification failed")

        # 3. Live Re-validation and Conflict Analysis
        kind = "RULE" if "RULE" in proposal.kind else "STRATEGY"
        val_res = await self.validator.validate(session, proposal.payload)
        new_blockers = [issue.message for issue in val_res.issues if issue.level == "ERROR"]

        conflicts = await self.conflict_analyzer.analyze_conflicts(session, kind, proposal.payload)
        for c in conflicts:
            if c.get("severity") == "BLOCKER":
                new_blockers.append(c.get("message"))

        if new_blockers:
            proposal.proposalStatus = "FAILED"
            proposal.failureReason = f"New blockers detected at confirm time: {'; '.join(new_blockers)}"
            await self.proposal_repo.save(session, proposal)
            raise ConflictException(message=f"Confirmation failed due to blockers: {'; '.join(new_blockers)}")

        # 4. Check warning acknowledgements
        warning_codes = [c.get("code") for c in proposal.complications if c.get("severity") == "WARNING"]
        unacknowledged = [code for code in warning_codes if code not in acknowledged_codes]
        if unacknowledged:
            raise ValidationException(
                message=f"All warning complications must be acknowledged before confirming. Missing: {unacknowledged}"
            )

        # 5. Check typed phrase for BLOCK / REQUIRE activation
        if mode == "ADD_AND_ACTIVATE":
            action = proposal.payload.get("action", "")
            target_code = proposal.targetCode or proposal.payload.get("code", "")
            if action in ["BLOCK", "REQUIRE"]:
                expected = f"ACTIVATE {target_code}"
                if typed_phrase != expected:
                    raise ValidationException(
                        message=f"Activating high-priority rule requires typing '{expected}'. Got: '{typed_phrase}'"
                    )

        # 6. Execute in transaction
        provenance = {
            "source": "MASTER_CHAT",
            "conversationId": proposal.conversationId,
            "proposalId": proposal.id,
            "userText": proposal.userText,
            "backTranslation": proposal.backTranslation,
        }

        try:
            result_refs = await self.executor.execute(
                session=session,
                kind=proposal.kind,
                payload=proposal.payload,
                target_code=proposal.targetCode,
                mode=mode,
                provenance=provenance,
            )
            proposal.resultRefs = result_refs
            proposal.confirmMode = mode
            proposal.confirmedAt = now
            proposal.proposalStatus = "CONFIRMED"
            saved_proposal = await self.proposal_repo.save(session, proposal)

            # Post a confirmation message in the conversation thread
            seq = await self.message_repo.get_next_seq(session, proposal.conversationId)
            created_code = result_refs.get("code", proposal.targetCode or "Item")
            result_msg = MasterMessage(
                conversationId=proposal.conversationId,
                seq=seq,
                role="ASSISTANT",
                content=(
                    f"✅ **Proposal #{proposal.id} Confirmed!**\n\n"
                    f"Created `{created_code}` in lifecycle state `{result_refs.get('lifecycleStatus', 'DRAFT')}`.\n\n"
                    f"*Reminder: Untested. No win rate or profitability claim is implied.*"
                ),
                blocks=[{
                    "type": "RESULT",
                    "proposalId": proposal.id,
                    "resultRefs": result_refs,
                }],
            )
            await self.message_repo.save(session, result_msg)
            return saved_proposal

        except Exception as e:
            proposal.proposalStatus = "FAILED"
            proposal.failureReason = str(e)[:500]
            await self.proposal_repo.save(session, proposal)
            raise e

    async def reject(self, session: AsyncSession, proposal_id: int, reason: Optional[str] = None) -> MasterProposal:
        proposal = await self.get_by_id(session, proposal_id)
        if proposal.proposalStatus != "PENDING":
            raise ConflictException(message=f"Proposal is already {proposal.proposalStatus}")
        proposal.proposalStatus = "REJECTED"
        proposal.failureReason = reason
        return await self.proposal_repo.save(session, proposal)

    async def revalidate(self, session: AsyncSession, proposal_id: int) -> MasterProposal:
        proposal = await self.get_by_id(session, proposal_id)
        kind = "RULE" if "RULE" in proposal.kind else "STRATEGY"
        val_res = await self.validator.validate(session, proposal.payload)
        conflicts = await self.conflict_analyzer.analyze_conflicts(session, kind, proposal.payload)

        proposal.validation = val_res.model_dump()
        comps = [c for c in proposal.complications if c.get("code") not in ["SCHEMA_INVALID", "VALIDATION_WARNING"]]
        for issue in val_res.issues:
            comps.append({
                "code": "SCHEMA_INVALID" if issue.level == "ERROR" else "VALIDATION_WARNING",
                "severity": "BLOCKER" if issue.level == "ERROR" else "WARNING",
                "message": issue.message,
                "path": issue.path,
            })
        for conf in conflicts:
            comps.append(conf)
        proposal.complications = comps
        return await self.proposal_repo.save(session, proposal)
