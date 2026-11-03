import { z } from "zod";

export const sessionCreateSchema = z
  .object({
    name: z.string().max(150).optional().or(z.literal("")),
    tradeDate: z.string().min(10), // always set to today (IST) by the dialog, not user-editable
    userId: z.coerce.number().int().positive("Select a user"),
    capital: z.coerce.number().positive("Capital must be greater than 0"),
    maxLossPercentage: z.coerce.number().positive().max(100).default(3),
    scope: z.enum(["INDEX", "COMMODITY"]),
    underlyings: z.array(z.string()).default([]),
    commodityItems: z.array(z.string()).default([]),
    sessionType: z.enum(["FULL_AUTO", "SEMI_AUTO", "MANUAL"]).default("MANUAL"),
    routeThroughUpstox: z.boolean().default(false),
  })
  .refine((v) => v.scope !== "INDEX" || v.underlyings.length > 0, {
    message: "Select at least one index underlying",
    path: ["underlyings"],
  })
  .refine((v) => v.scope !== "COMMODITY" || v.commodityItems.length > 0, {
    message: "Select at least one commodity",
    path: ["commodityItems"],
  });

export type SessionCreateFormValues = z.infer<typeof sessionCreateSchema>;
