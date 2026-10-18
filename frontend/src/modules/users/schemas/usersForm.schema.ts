import { z } from "zod";

export const userCreateSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(100, "Name must not exceed 100 characters"),
  apiKey: z.string().min(1, "Upstox API Key is required"),
  apiSecret: z.string().min(1, "Upstox API Secret is required"),
  mobile: z
    .string()
    .min(10, "Mobile number must be at least 10 digits")
    .max(15, "Mobile number too long"),
  pin: z.string().min(4, "PIN must be at least 4 digits"),
  totpSecret: z.string().min(1, "TOTP secret is required for auto-auth"),
  autoAuthEnabled: z.boolean().default(true),
});

export type UserCreateFormValues = z.infer<typeof userCreateSchema>;

export const userUpdateSchema = z.object({
  name: z
    .string()
    .min(1, "Name is required")
    .max(100, "Name must not exceed 100 characters"),
  apiKey: z.string().min(1, "Upstox API Key is required"),
  apiSecret: z.string().optional().or(z.literal("")),
  mobile: z
    .string()
    .min(10, "Mobile number must be at least 10 digits")
    .max(15, "Mobile number too long"),
  pin: z.string().optional().or(z.literal("")),
  totpSecret: z.string().optional().or(z.literal("")),
  autoAuthEnabled: z.boolean().default(true),
});

export type UserUpdateFormValues = z.infer<typeof userUpdateSchema>;
