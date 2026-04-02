import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { describe, expect, it } from "vitest";

function hexToRgb(hex: string): [number, number, number] {
  const normalized = hex.trim().replace(/^#/, "");
  if (!/^[0-9a-f]{6}$/i.test(normalized)) {
    throw new Error(`Expected 6-digit hex color, got: ${hex}`);
  }
  return [
    Number.parseInt(normalized.slice(0, 2), 16),
    Number.parseInt(normalized.slice(2, 4), 16),
    Number.parseInt(normalized.slice(4, 6), 16),
  ];
}

function srgbToLinear(channel: number): number {
  const c = channel / 255;
  return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
}

function relativeLuminance(hex: string): number {
  const [r, g, b] = hexToRgb(hex);
  const [rl, gl, bl] = [r, g, b].map(srgbToLinear);
  return 0.2126 * rl + 0.7152 * gl + 0.0722 * bl;
}

function contrastRatio(foregroundHex: string, backgroundHex: string): number {
  const l1 = relativeLuminance(foregroundHex);
  const l2 = relativeLuminance(backgroundHex);
  const lighter = Math.max(l1, l2);
  const darker = Math.min(l1, l2);
  return (lighter + 0.05) / (darker + 0.05);
}

function readCssToken(css: string, tokenName: string): string {
  const tokenPattern = new RegExp(`${tokenName}\\s*:\\s*(#[0-9a-fA-F]{6})\\s*;`);
  const match = css.match(tokenPattern);
  if (!match) {
    throw new Error(`Missing CSS token: ${tokenName}`);
  }
  return match[1];
}

describe("styles accessibility", () => {
  it("keeps muted label text readable on page and card backgrounds", () => {
    const css = readFileSync(resolve(__dirname, "./styles.css"), "utf8");
    const inkMuted = readCssToken(css, "--ink-muted");
    const pageBg = readCssToken(css, "--bg");
    const cardBg = readCssToken(css, "--card");

    expect(contrastRatio(inkMuted, pageBg)).toBeGreaterThanOrEqual(4.5);
    expect(contrastRatio(inkMuted, cardBg)).toBeGreaterThanOrEqual(4.5);
  });
});
