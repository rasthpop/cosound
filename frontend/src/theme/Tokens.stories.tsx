// Token gallery: every semantic token of the active theme. Names come from the TS tokens; colours
// are read through the generated CSS variables, so the toolbar (or a story's `globals.theme`)
// switches what is shown. Runs with axe in both themes (npm run test-storybook).
import type { Meta, StoryObj } from "@storybook/react-vite";
import type { CSSProperties, ReactNode } from "react";

import { dark } from "./tokens/semantic";

// Literal class names: Tailwind only generates utilities it can find in the source.
const SIZE_CLASS = { display: "text-display", heading: "text-heading", body: "text-body", meta: "text-meta" } as const;
const RADIUS_CLASS = { sm: "rounded-sm", md: "rounded-md", lg: "rounded-lg", pill: "rounded-pill" } as const;

const kebab = (s: string) => s.replace(/([a-z0-9])([A-Z])/g, "$1-$2").toLowerCase();
const cssVar = (...path: string[]) => `var(--token-${path.map(kebab).join("-")})`;

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section aria-labelledby={`tokens-${kebab(title)}`} className="flex flex-col gap-1.5">
      <h2 id={`tokens-${kebab(title)}`} className="text-heading font-medium">
        {title}
      </h2>
      {children}
    </section>
  );
}

function Swatch({ name, background, ring }: { name: string; background: string; ring?: boolean }) {
  const style: CSSProperties = { background };
  if (ring) style.boxShadow = `inset 0 0 0 1px ${cssVar("color", "border", "strong")}`;
  return (
    <li className="flex w-20 flex-col gap-0.5">
      <span aria-hidden="true" className="block h-6 rounded-md" style={style} />
      <span className="text-meta text-muted">{name}</span>
    </li>
  );
}

function ColorGroup({ group }: { group: keyof typeof dark.color }) {
  const entries = dark.color[group];
  const names = Object.keys(entries).filter((k) => typeof (entries as Record<string, unknown>)[k] === "string");
  return (
    <div className="flex flex-col gap-1">
      <h3 className="text-body font-medium">{group}</h3>
      <ul className="flex flex-wrap gap-2">
        {names.map((name) => (
          <Swatch key={name} name={name} background={cssVar("color", group, name)} ring />
        ))}
      </ul>
    </div>
  );
}

function Gallery() {
  const groups = Object.keys(dark.color) as (keyof typeof dark.color)[];
  return (
    <main className="bg-surface-canvas text-fg flex min-h-dvh flex-col gap-4 p-4">
      <h1 className="text-display font-medium">Design tokens</h1>

      <Section title="Colour">
        {groups.map((g) => (
          <ColorGroup key={g} group={g} />
        ))}
        <div className="flex flex-col gap-1">
          <h3 className="text-body font-medium">map point</h3>
          <ul className="flex flex-wrap gap-2">
            {Object.keys(dark.color.map.point).map((name) => (
              <Swatch key={name} name={name} background={cssVar("color", "map", "point", name)} ring />
            ))}
          </ul>
        </div>
        <div className="flex flex-col gap-1">
          <h3 className="text-body font-medium">map genre palette (slots 1–8)</h3>
          <ul className="flex flex-wrap gap-2">
            {dark.color.map.categorical.map((_, i) => (
              <Swatch key={i} name={`slot ${i + 1}`} background={cssVar("color", "map", "categorical", String(i))} />
            ))}
          </ul>
        </div>
      </Section>

      <Section title="Glass panel">
        <div className="bg-surface-panel border-hairline backdrop-blur-panel rounded-lg border p-2">
          <p className="text-body font-medium">Track title · 15/500</p>
          <p className="text-meta text-muted">Artist · genre · 13/400 muted</p>
          <button type="button" className="bg-accent text-on-accent rounded-md mt-1 px-2 py-0.5 font-medium">
            Primary action
          </button>
        </div>
      </Section>

      <Section title="Typography">
        {(["display", "heading", "body", "meta"] as const).map((size) => (
          <p key={size} className={SIZE_CLASS[size]}>
            {size} · {dark.font.size[size]}px / {dark.font.lineHeight[size]}px
          </p>
        ))}
        <p className="text-body font-regular">regular · {dark.font.weight.regular}</p>
        <p className="text-body font-medium">medium · {dark.font.weight.medium}</p>
      </Section>

      <Section title="Radius and spacing">
        <ul className="flex flex-wrap gap-2">
          {(Object.keys(dark.radius) as (keyof typeof dark.radius)[]).map((r) => (
            <li key={r} className="flex flex-col gap-0.5">
              <span aria-hidden="true" className={`bg-surface-raised border-border-strong block h-6 w-12 border ${RADIUS_CLASS[r]}`} />
              <span className="text-meta text-muted">
                radius {r} · {dark.radius[r]}px
              </span>
            </li>
          ))}
        </ul>
        <ul className="flex flex-col gap-0.5">
          {Object.entries(dark.space).map(([name, px]) => (
            <li key={name} className="flex items-center gap-1">
              <span aria-hidden="true" className="bg-accent-subtle block h-1" style={{ width: cssVar("space", name) }} />
              <span className="text-meta text-muted">
                space {name} · {px}px
              </span>
            </li>
          ))}
        </ul>
      </Section>
    </main>
  );
}

const meta = {
  title: "Theme/Tokens",
  component: Gallery,
} satisfies Meta<typeof Gallery>;

export default meta;
type Story = StoryObj<typeof meta>;

export const Dark: Story = { globals: { theme: "dark" } };
export const Light: Story = { globals: { theme: "light" } };
