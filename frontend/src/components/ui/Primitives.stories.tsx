// The shadcn primitives on tokens, in both themes. Overlay primitives have their own stories,
// rendered open, so axe checks their open state too.
import type { Meta, StoryObj } from "@storybook/react-vite";
import { Bold, Play } from "lucide-react";

import { ICON } from "@/theme/tokens/semantic";

import { Badge } from "./badge";
import { Button } from "./button";
import { Drawer, DrawerContent, DrawerDescription, DrawerHeader, DrawerTitle } from "./drawer";
import { Input } from "./input";
import { Popover, PopoverContent, PopoverDescription, PopoverHeader, PopoverTitle, PopoverTrigger } from "./popover";
import { ScrollArea } from "./scroll-area";
import { Separator } from "./separator";
import { Sheet, SheetContent, SheetDescription, SheetHeader, SheetTitle } from "./sheet";
import { Skeleton } from "./skeleton";
import { Toggle } from "./toggle";
import { Tooltip, TooltipContent, TooltipTrigger } from "./tooltip";

function Gallery() {
  return (
    <main className="flex min-h-dvh flex-col gap-3 bg-surface-canvas p-3 text-fg">
      <h1 className="text-heading font-medium">Primitives</h1>
      <section aria-label="Buttons" className="flex flex-wrap items-center gap-1">
        <Button variant="primary">Search</Button>
        <Button>Secondary</Button>
        <Button variant="ghost">Ghost</Button>
        <Button variant="quiet">Quiet</Button>
        <Button variant="link">Open on FMA</Button>
        <Button size="sm">Small</Button>
        <Button size="icon" aria-label="Play preview">
          <Play aria-hidden="true" {...ICON} />
        </Button>
        <Button disabled>Disabled</Button>
      </section>
      <section aria-label="Input" className="flex max-w-80 flex-col gap-1">
        <label htmlFor="primitive-input" className="text-meta text-muted">
          Describe a sound
        </label>
        <Input id="primitive-input" placeholder="something chill with a flute" />
      </section>
      <section aria-label="Badges" className="flex flex-wrap gap-1">
        <Badge>Folk</Badge>
        <Badge variant="outline">Hard constraint</Badge>
        <Badge variant="accent">Selected</Badge>
      </section>
      <section aria-label="Toggle" className="flex gap-1">
        <Toggle aria-label="Refine">Refine</Toggle>
        <Toggle aria-label="Bold" defaultPressed>
          <Bold aria-hidden="true" {...ICON} />
        </Toggle>
      </section>
      <Separator />
      <section aria-label="Scroll area">
        <ScrollArea className="h-12 w-40 rounded-md border border-hairline">
          <ol className="flex flex-col gap-0.5 p-1 text-meta">
            {Array.from({ length: 20 }, (_, i) => (
              <li key={i}>Track {i + 1}</li>
            ))}
          </ol>
        </ScrollArea>
      </section>
      <section aria-label="Loading" className="flex flex-col gap-1">
        <Skeleton className="h-2 w-30" />
        <Skeleton className="h-2 w-20" />
      </section>
    </main>
  );
}

const meta = { title: "Primitives/Gallery", component: Gallery } satisfies Meta<typeof Gallery>;
export default meta;
type Story = StoryObj<typeof meta>;

export const Dark: Story = { globals: { theme: "dark" } };
export const Light: Story = { globals: { theme: "light" } };

const Canvas = ({ children }: { children: React.ReactNode }) => (
  <main className="flex min-h-dvh items-start justify-center bg-surface-canvas p-6 text-fg">{children}</main>
);

export const TooltipOpen: Story = {
  render: () => (
    <Canvas>
      <Tooltip open>
        <TooltipTrigger asChild>
          <Button>Hover me</Button>
        </TooltipTrigger>
        <TooltipContent>Night Train · Artist nocturne · Electronic</TooltipContent>
      </Tooltip>
    </Canvas>
  ),
};

export const PopoverOpen: Story = {
  render: () => (
    <Canvas>
      <Popover open>
        <PopoverTrigger asChild>
          <Button>Wrong instrument…</Button>
        </PopoverTrigger>
        <PopoverContent aria-labelledby="popover-title">
          <PopoverHeader>
            <PopoverTitle id="popover-title">Which instrument is wrong?</PopoverTitle>
            <PopoverDescription>From your search</PopoverDescription>
          </PopoverHeader>
          <Button variant="ghost" size="sm">
            flute
          </Button>
        </PopoverContent>
      </Popover>
    </Canvas>
  ),
};

export const SheetOpen: Story = {
  render: () => (
    <Canvas>
      <Sheet open modal={false}>
        <SheetContent overlay={false} onInteractOutside={(e) => e.preventDefault()}>
          <SheetHeader>
            <SheetTitle>Night Train</SheetTitle>
            <SheetDescription>Artist nocturne · Electronic</SheetDescription>
          </SheetHeader>
          <p className="text-body">Details drawer content.</p>
        </SheetContent>
      </Sheet>
    </Canvas>
  ),
};

export const DrawerOpen: Story = {
  render: () => (
    <Canvas>
      <Drawer open>
        <DrawerContent className="h-1/2">
          <DrawerHeader>
            <DrawerTitle>12 tracks</DrawerTitle>
            <DrawerDescription>something chill with a flute</DrawerDescription>
          </DrawerHeader>
        </DrawerContent>
      </Drawer>
    </Canvas>
  ),
};

export const OverlaysLight: Story = {
  globals: { theme: "light" },
  render: () => (
    <Canvas>
      <Popover open>
        <PopoverTrigger asChild>
          <Button>Menu</Button>
        </PopoverTrigger>
        <PopoverContent aria-label="Light glass">
          <PopoverTitle>Light glass</PopoverTitle>
          <PopoverDescription>Muted text on the light panel</PopoverDescription>
        </PopoverContent>
      </Popover>
    </Canvas>
  ),
};
