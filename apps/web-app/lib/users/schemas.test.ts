import { describe, expect, it } from "vitest";
import {
  acceptInvitationSchema,
  inviteMemberSchema,
  rolesAssignableBy,
  updateMemberSchema,
} from "./schemas";

describe("inviteMemberSchema", () => {
  it("aceita email valido e role existente", () => {
    const r = inviteMemberSchema.safeParse({
      email: "novo@tenant.com",
      role: "operator",
    });
    expect(r.success).toBe(true);
  });

  it("rejeita email invalido", () => {
    const r = inviteMemberSchema.safeParse({
      email: "sem-arroba",
      role: "viewer",
    });
    expect(r.success).toBe(false);
  });

  it("rejeita role invalida", () => {
    const r = inviteMemberSchema.safeParse({
      email: "a@b.com",
      role: "superuser",
    });
    expect(r.success).toBe(false);
  });
});

describe("updateMemberSchema", () => {
  it("aceita qualquer role valida", () => {
    for (const role of ["owner", "admin", "operator", "viewer"] as const) {
      expect(updateMemberSchema.safeParse({ role }).success).toBe(true);
    }
  });

  it("rejeita role vazia", () => {
    expect(updateMemberSchema.safeParse({ role: "" }).success).toBe(false);
  });
});

describe("acceptInvitationSchema", () => {
  it("aceita payload valido com senhas iguais", () => {
    const r = acceptInvitationSchema.safeParse({
      name: "Fulano de Tal",
      password: "segredo-forte-123",
      confirm: "segredo-forte-123",
    });
    expect(r.success).toBe(true);
  });

  it("rejeita senhas diferentes", () => {
    const r = acceptInvitationSchema.safeParse({
      name: "Fulano",
      password: "segredo-forte-123",
      confirm: "outra-coisa-123",
    });
    expect(r.success).toBe(false);
  });

  it("rejeita senha curta", () => {
    const r = acceptInvitationSchema.safeParse({
      name: "Fulano",
      password: "curta",
      confirm: "curta",
    });
    expect(r.success).toBe(false);
  });
});

describe("rolesAssignableBy", () => {
  it("owner pode atribuir qualquer papel", () => {
    expect(rolesAssignableBy("owner")).toEqual([
      "owner",
      "admin",
      "operator",
      "viewer",
    ]);
  });

  it("admin so pode atribuir operator e viewer", () => {
    expect(rolesAssignableBy("admin")).toEqual(["operator", "viewer"]);
  });

  it("operator/viewer nao podem atribuir papeis", () => {
    expect(rolesAssignableBy("operator")).toEqual([]);
    expect(rolesAssignableBy("viewer")).toEqual([]);
  });
});
