"""One-time script to add deprecation callouts to old monolithic API files."""
import pathlib

VAULT = pathlib.Path(__file__).resolve().parent.parent / "obsidian" / "APIs"

OLD_FILES = {
    "Health API.md": "Health",
    "Projects API.md": "Projects",
    "Ideas API.md": "Ideas",
    "PRD Flow API.md": "PRD Flow",
    "Publishing API.md": "Publishing",
    "Slack API.md": "Slack",
    "SSO Webhooks API.md": "SSO Webhooks",
}

CALLOUT = """> [!warning] Deprecated — Use Per-Route Files
> This monolithic file is superseded by individual per-route files in [[{folder}/]].
> Each endpoint now has its own file with detailed request, response, and database algorithm.
> **Edit the per-route files instead.** This file is kept for historical reference only.

---

"""


def main():
    count = 0
    for filename, folder in OLD_FILES.items():
        fpath = VAULT / filename
        if not fpath.exists():
            print(f"  SKIP (not found): {filename}")
            continue
        text = fpath.read_text()

        # Don't add twice
        if "Deprecated" in text and "Per-Route Files" in text:
            print(f"  SKIP (already deprecated): {filename}")
            continue

        # Find the first heading (after frontmatter)
        if text.startswith("---\n"):
            # Find end of frontmatter
            end_fm = text.index("---\n", 4) + 4
            before = text[:end_fm]
            after = text[end_fm:].lstrip("\n")
        else:
            before = ""
            after = text

        # Find the first # heading
        lines = after.split("\n")
        heading_idx = None
        for i, line in enumerate(lines):
            if line.startswith("# "):
                heading_idx = i
                break

        if heading_idx is not None:
            # Insert callout after heading and its description
            # Find end of heading block (next blank line or section)
            insert_after = heading_idx + 1
            # Skip description line if present
            while insert_after < len(lines) and lines[insert_after].startswith(">"):
                insert_after += 1
            # Skip blank lines
            while insert_after < len(lines) and lines[insert_after].strip() == "":
                insert_after += 1

            callout = CALLOUT.format(folder=folder)
            lines.insert(insert_after, callout)
            after = "\n".join(lines)

        fpath.write_text(before + "\n" + after)
        print(f"  + {filename} → deprecated (points to {folder}/)")
        count += 1

    print(f"\nDone: {count} files updated")


if __name__ == "__main__":
    main()
