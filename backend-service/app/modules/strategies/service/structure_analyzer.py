from typing import Any, Dict, List, Optional


class StructureAnalyzer:
    """
    Deterministic structure and risk analyzer for trading strategies.
    Analyzes legs, classifies options structure, determines risk definition, and computes max loss formula.
    """

    @classmethod
    def analyze(cls, definition: Dict[str, Any]) -> Dict[str, Any]:
        if not definition or not isinstance(definition, dict):
            return {
                "structure": "UNKNOWN",
                "bias": "NEUTRAL",
                "riskType": "UNDEFINED_RISK",
                "premiumType": "NEUTRAL",
                "maxLossFormula": "Unknown definition structure",
                "legs": [],
                "notes": ["Invalid or empty definition"],
            }

        cases = definition.get("cases", [])
        if not cases:
            return {
                "structure": "UNKNOWN",
                "bias": "NEUTRAL",
                "riskType": "UNDEFINED_RISK",
                "premiumType": "NEUTRAL",
                "maxLossFormula": "No cases defined",
                "legs": [],
                "notes": ["No execution cases found in strategy definition"],
            }

        # Analyze legs across all cases (primary focus on case 0)
        first_case = cases[0]
        legs_data = first_case.get("entry", {}).get("legs", [])

        analyzed_legs: List[Dict[str, Any]] = []
        option_legs: List[Dict[str, Any]] = []
        equity_future_legs: List[Dict[str, Any]] = []

        has_unhedged_short_option = False
        has_stop_loss_on_all_shorts = True

        for leg in legs_data:
            leg_id = leg.get("legId", "1")
            side = leg.get("side", "BUY").upper()
            inst = leg.get("instrument", {})
            kind = inst.get("kind", "OPTION").upper()
            qty = leg.get("quantity", {}).get("value", 1)
            sl = leg.get("stopLoss")
            tgt = leg.get("target")

            analyzed_leg = {
                "legId": leg_id,
                "side": side,
                "kind": kind,
                "quantity": qty,
                "hasStop": sl is not None,
                "hasTarget": tgt is not None,
                "stopLoss": sl,
                "target": tgt,
            }

            if kind == "OPTION":
                opt_type = inst.get("optionType", "CE").upper()
                strike = inst.get("strike", {})
                selector = strike.get("selector", "ATM")
                steps = strike.get("steps", 0)

                analyzed_leg.update({
                    "optionType": opt_type,
                    "strikeSelector": selector,
                    "strikeSteps": steps,
                    "expiryCycle": inst.get("expiry", {}).get("cycle", "WEEKLY"),
                })
                option_legs.append(analyzed_leg)

                if side == "SELL":
                    if not sl:
                        has_stop_loss_on_all_shorts = False
            else:
                equity_future_legs.append(analyzed_leg)

            analyzed_legs.append(analyzed_leg)

        # Classify options structure
        structure = "CUSTOM"
        bias = "NEUTRAL"
        premium_type = "NEUTRAL"
        risk_type = "DEFINED_RISK"
        max_loss_formula = "Limited by defined stops"
        notes: List[str] = []

        num_opt = len(option_legs)
        if num_opt == 0:
            if equity_future_legs:
                first_leg = equity_future_legs[0]
                if first_leg["side"] == "BUY":
                    structure = "LONG_ASSET"
                    bias = "BULLISH"
                    premium_type = "NET_DEBIT"
                else:
                    structure = "SHORT_ASSET"
                    bias = "BEARISH"
                    premium_type = "NET_CREDIT"

                if first_leg["hasStop"]:
                    risk_type = "DEFINED_RISK"
                    max_loss_formula = "Max Loss = (Entry Price - Stop Loss Price) * Quantity"
                else:
                    risk_type = "UNDEFINED_RISK" if first_leg["side"] == "SELL" else "DEFINED_RISK"
                    max_loss_formula = "Unlimited risk on unhedged short position" if first_leg["side"] == "SELL" else "Total capital allocated"

        elif num_opt == 1:
            opt = option_legs[0]
            side = opt["side"]
            opt_type = opt["optionType"]
            if side == "BUY":
                premium_type = "NET_DEBIT"
                if opt_type == "CE":
                    structure = "LONG_CALL"
                    bias = "BULLISH"
                else:
                    structure = "LONG_PUT"
                    bias = "BEARISH"
                risk_type = "DEFINED_RISK"
                if opt["hasStop"]:
                    max_loss_formula = f"Max Loss = Premium Paid * Stop Loss % ({opt['stopLoss'].get('value')}%) * Lot Size"
                else:
                    max_loss_formula = "Max Loss = 100% of Entry Premium Paid * Lot Size"
            else:
                # Sold single leg
                premium_type = "NET_CREDIT"
                has_unhedged_short_option = True
                if opt_type == "CE":
                    structure = "SHORT_CALL"
                    bias = "BEARISH"
                else:
                    structure = "SHORT_PUT"
                    bias = "BULLISH"

                if opt["hasStop"]:
                    risk_type = "DEFINED_RISK"
                    max_loss_formula = f"Max Loss = Entry Premium * Stop Loss % ({opt['stopLoss'].get('value')}%) * Lot Size"
                    notes.append("Sold option risk defined via stop loss order")
                else:
                    risk_type = "UNDEFINED_RISK"
                    max_loss_formula = "Unlimited risk (Naked short option without hedge or stop loss)"
                    notes.append("CRITICAL: Naked short option has undefined risk")

        elif num_opt == 2:
            leg_a, leg_b = option_legs[0], option_legs[1]
            sides = {leg_a["side"], leg_b["side"]}
            types = {leg_a["optionType"], leg_b["optionType"]}

            if sides == {"BUY", "SELL"} and len(types) == 1:
                # Vertical spread
                opt_t = list(types)[0]
                buy_leg = leg_a if leg_a["side"] == "BUY" else leg_b
                sell_leg = leg_b if leg_a["side"] == "BUY" else leg_a

                if opt_t == "CE":
                    if buy_leg["strikeSteps"] < sell_leg["strikeSteps"]:
                        structure = "BULL_CALL_SPREAD"
                        bias = "BULLISH"
                        premium_type = "NET_DEBIT"
                        max_loss_formula = "Max Loss = Net Debit Paid * Lot Size"
                    else:
                        structure = "BEAR_CALL_SPREAD"
                        bias = "BEARISH"
                        premium_type = "NET_CREDIT"
                        max_loss_formula = "Max Loss = (Strike Difference - Net Credit) * Lot Size"
                else:
                    if buy_leg["strikeSteps"] > sell_leg["strikeSteps"]:
                        structure = "BEAR_PUT_SPREAD"
                        bias = "BEARISH"
                        premium_type = "NET_DEBIT"
                        max_loss_formula = "Max Loss = Net Debit Paid * Lot Size"
                    else:
                        structure = "BULL_PUT_SPREAD"
                        bias = "BULLISH"
                        premium_type = "NET_CREDIT"
                        max_loss_formula = "Max Loss = (Strike Difference - Net Credit) * Lot Size"
                risk_type = "DEFINED_RISK"

            elif sides == {"BUY"} and types == {"CE", "PE"}:
                # Long straddle or strangle
                if leg_a["strikeSteps"] == leg_b["strikeSteps"]:
                    structure = "LONG_STRADDLE"
                else:
                    structure = "LONG_STRANGLE"
                bias = "NEUTRAL"
                premium_type = "NET_DEBIT"
                risk_type = "DEFINED_RISK"
                max_loss_formula = "Max Loss = Total Combined Premium Paid * Lot Size"

            elif sides == {"SELL"} and types == {"CE", "PE"}:
                # Short straddle or strangle
                if leg_a["strikeSteps"] == leg_b["strikeSteps"]:
                    structure = "SHORT_STRADDLE"
                else:
                    structure = "SHORT_STRANGLE"
                bias = "NEUTRAL"
                premium_type = "NET_CREDIT"
                has_unhedged_short_option = True

                if has_stop_loss_on_all_shorts:
                    risk_type = "DEFINED_RISK"
                    max_loss_formula = "Max Loss capped by stop loss on both legs"
                    notes.append("Short straddle/strangle risk bounded by stop loss orders")
                else:
                    risk_type = "UNDEFINED_RISK"
                    max_loss_formula = "Unlimited risk (Naked short straddle/strangle without hedges)"
                    notes.append("CRITICAL: Naked short strangle/straddle without protective hedges or stops")

        elif num_opt == 4:
            sells = [l for l in option_legs if l["side"] == "SELL"]
            buys = [l for l in option_legs if l["side"] == "BUY"]
            if len(sells) == 2 and len(buys) == 2:
                structure = "IRON_CONDOR"
                bias = "NEUTRAL"
                premium_type = "NET_CREDIT"
                risk_type = "DEFINED_RISK"
                max_loss_formula = "Max Loss = (Wing Width - Net Credit) * Lot Size"
                notes.append("Hedged 4-leg credit structure with defined risk")

        return {
            "structure": structure,
            "bias": bias,
            "riskType": risk_type,
            "premiumType": premium_type,
            "maxLossFormula": max_loss_formula,
            "hasUnhedgedShort": has_unhedged_short_option and not has_stop_loss_on_all_shorts,
            "legs": analyzed_legs,
            "notes": notes,
        }
