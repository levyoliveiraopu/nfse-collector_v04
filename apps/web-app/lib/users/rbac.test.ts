import { describe, expect, it } from "vitest";
import {
  canChangeRole,
  canInviteWithRole,
  canRemoveMember,
  canRevokeInvitation,
  isManager,
  roleRank,
} from "./rbac";
import type { Role } from "./types";

const ALL_ROLES: Role[] = ["owner", "admin", "operator", "viewer"];

describe("roleRank / isManager", () => {
  it("ranqueia papeis na ordem esperada", () => {
    expect(roleRank("owner")).toBe(4);
    expect(roleRank("admin")).toBe(3);
    expect(roleRank("operator")).toBe(2);
    expect(roleRank("viewer")).toBe(1);
  });

  it("apenas owner e admin sao managers", () => {
    expect(isManager("owner")).toBe(true);
    expect(isManager("admin")).toBe(true);
    expect(isManager("operator")).toBe(false);
    expect(isManager("viewer")).toBe(false);
  });
});

describe("canRemoveMember", () => {
  it("viewer e operator nunca removem ninguem", () => {
    for (const actor of ["operator", "viewer"] as Role[]) {
      for (const target of ALL_ROLES) {
        const d = canRemoveMember(actor, target);
        expect(d.allowed).toBe(false);
      }
    }
  });

  it("admin nao remove owner", () => {
    const d = canRemoveMember("admin", "owner");
    expect(d.allowed).toBe(false);
    if (!d.allowed) expect(d.reason).toMatch(/owner pode gerenciar outro owner/);
  });

  it("admin remove admin/operator/viewer", () => {
    expect(canRemoveMember("admin", "admin").allowed).toBe(true);
    expect(canRemoveMember("admin", "operator").allowed).toBe(true);
    expect(canRemoveMember("admin", "viewer").allowed).toBe(true);
  });

  it("owner remove qualquer papel", () => {
    for (const target of ALL_ROLES) {
      expect(canRemoveMember("owner", target).allowed).toBe(true);
    }
  });
});

describe("canChangeRole", () => {
  it("admin nao altera papel de owner", () => {
    const d = canChangeRole("admin", "owner", "admin");
    expect(d.allowed).toBe(false);
  });

  it("admin nao promove a admin nem a owner", () => {
    expect(canChangeRole("admin", "operator", "admin").allowed).toBe(false);
    expect(canChangeRole("admin", "operator", "owner").allowed).toBe(false);
  });

  it("admin pode rebaixar admin para operator/viewer", () => {
    expect(canChangeRole("admin", "admin", "operator").allowed).toBe(true);
    expect(canChangeRole("admin", "admin", "viewer").allowed).toBe(true);
  });

  it("owner pode promover a qualquer papel", () => {
    expect(canChangeRole("owner", "viewer", "owner").allowed).toBe(true);
    expect(canChangeRole("owner", "operator", "admin").allowed).toBe(true);
  });

  it("operator/viewer nao alteram papel de ninguem", () => {
    for (const actor of ["operator", "viewer"] as Role[]) {
      expect(canChangeRole(actor, "viewer", "operator").allowed).toBe(false);
    }
  });
});

describe("canInviteWithRole", () => {
  it("admin nao pode convidar para owner nem admin", () => {
    expect(canInviteWithRole("admin", "owner").allowed).toBe(false);
    expect(canInviteWithRole("admin", "admin").allowed).toBe(false);
  });

  it("admin convida operator/viewer", () => {
    expect(canInviteWithRole("admin", "operator").allowed).toBe(true);
    expect(canInviteWithRole("admin", "viewer").allowed).toBe(true);
  });

  it("owner convida qualquer papel", () => {
    for (const role of ALL_ROLES) {
      expect(canInviteWithRole("owner", role).allowed).toBe(true);
    }
  });

  it("non-manager sempre negado", () => {
    expect(canInviteWithRole("operator", "viewer").allowed).toBe(false);
    expect(canInviteWithRole("viewer", "viewer").allowed).toBe(false);
  });
});

describe("canRevokeInvitation", () => {
  it("segue as mesmas regras de remocao de membro", () => {
    expect(canRevokeInvitation("admin", "owner").allowed).toBe(false);
    expect(canRevokeInvitation("owner", "owner").allowed).toBe(true);
    expect(canRevokeInvitation("operator", "viewer").allowed).toBe(false);
    expect(canRevokeInvitation("admin", "viewer").allowed).toBe(true);
  });
});
