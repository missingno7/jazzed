# OpenJazz Reference

OpenJazz is useful when figuring out how original Jazz Jackrabbit 1 data is interpreted. Jazzed uses that source code as a reference during development, not as a runtime dependency.

## Repository Policy

The public Jazzed repository should not include an OpenJazz checkout.

Local folders ignored by git:

```text
openjazz/
OpenJazz/
```

## How To Use A Local Checkout

If you have OpenJazz locally, keep it next to the editor source:

```text
jazzed/
  openjazz/
  jazzed_editor/
```

Then search it while implementing parser or behavior changes.

Useful areas in OpenJazz:

- JJ1 level loading
- tileset loading
- mask decoding
- palette/background effects
- event touch effects, movement behavior, and reserved marker IDs
- sound and tracker/module handling references
- event/player interaction code

## Important Distinction

Jazzed edits original DOS data files. It does not create or consume an OpenJazz-specific project format.

When documenting behavior, prefer wording like "OpenJazz-reference code" rather than implying OpenJazz is required by Jazzed.
