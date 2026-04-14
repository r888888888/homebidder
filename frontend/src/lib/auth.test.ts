import { describe, it, expect, beforeEach, vi } from "vitest";
import {
  getToken,
  setToken,
  clearToken,
  authHeaders,
} from "./auth";

// Storage is provided by jsdom; reset between tests.
beforeEach(() => {
  localStorage.clear();
});

describe("getToken / setToken / clearToken", () => {
  it("returns null when nothing is stored", () => {
    expect(getToken()).toBeNull();
  });

  it("returns the stored token after setToken", () => {
    setToken("my.jwt.token");
    expect(getToken()).toBe("my.jwt.token");
  });

  it("returns null after clearToken", () => {
    setToken("my.jwt.token");
    clearToken();
    expect(getToken()).toBeNull();
  });
});

describe("authHeaders", () => {
  it("returns empty object when no token is stored", () => {
    expect(authHeaders()).toEqual({});
  });

  it("returns Authorization header when token is present", () => {
    setToken("test.token.here");
    expect(authHeaders()).toEqual({ Authorization: "Bearer test.token.here" });
  });
});
