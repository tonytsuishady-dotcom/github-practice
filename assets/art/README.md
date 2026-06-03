# Codex Spirit Companion Art Kit

This folder keeps the first reusable art resources for the Codex spirit pet project.

## Reference

- `references/taotie-evolution-reference.png`
  - Five-stage Taotie evolution reference.
  - Use it as style direction, not as the runtime animation source.

## Sprite Direction

The runtime desktop pet is still programmatic. It is drawn in `desktop_pet.py` so the pet can react to keyboard input, feeding, digestion, sleep, and low-energy states.

Future sprite sheets should follow this direction:

- Jade green body.
- Warm cream belly.
- Antique gold horns.
- Coral blush.
- Thick dark outline.
- Small readable silhouette.
- Stable dress-up anchors: head, chest or neck charm, back item.

## Current Deployable Assets

- `sprites/taotie-mini.svg`: simple static mascot mark for README, web UI, or share-card drafts.
- `sprites/taotie-state-sheet.svg`: visual state sheet for the desktop pet's eight life states.
- `icons/jade-slip.svg`: small jade-slip icon for file feeding or output records.
- `states.json`: state labels, triggers, and visual notes for implementation/design sync.
- `tokens.css`: shared art colors and UI tokens.

`desktop_pet.py` reads `states.json` at runtime and maps the active pet state to an art-state label. The pet remains programmatically animated for now, but the state table is now part of the runtime handoff path.

The preview page `../../art-kit.html` uses `../../art-kit.js` to render:

- `states.json` into readable state cards.
- `manifest.json` into resource handoff cards.

Resource handoff cards show thumbnails for image/SVG assets and include a copy-path button.

## Privacy

Do not place user files, screenshots with private information, auth paths, token values, or real account identifiers in this folder.
