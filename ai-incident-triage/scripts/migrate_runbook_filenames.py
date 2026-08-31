import os
import re
import yaml
from pathlib import Path

RUNBOOKS_DIR = Path("knowledge_base/runbooks")

def _slugify_segment(text: str, max_length: int = 40, fallback: str = "unknown") -> str:
    if not text:
        return fallback
    text = str(text).lower()
    text = text[:max_length]
    text = re.sub(r'[^a-z0-9-]+', '-', text)
    text = re.sub(r'-+', '-', text)
    text = text.strip('-')
    return text or fallback

def migrate_filenames():
    if not RUNBOOKS_DIR.exists():
        print(f"Directory {RUNBOOKS_DIR} does not exist.")
        return

    migrated_count = 0
    for file_path in RUNBOOKS_DIR.glob("*.md"):
        content = file_path.read_text()
        
        # Check if it's auto-generated (YAML frontmatter + auto-generated owning team)
        if not (content.startswith("---") and "owning_team: auto-generated" in content):
            print(f"Skipping {file_path.name}: Not recognized as auto-generated.")
            continue
        
        # Extract metadata
        frontmatter_match = re.match(r'^---\n(.*?)\n---', content, re.DOTALL)
        if not frontmatter_match:
            print(f"Skipping {file_path.name}: Could not parse frontmatter.")
            continue
            
        try:
            metadata = yaml.safe_load(frontmatter_match.group(1))
        except Exception as e:
            print(f"Skipping {file_path.name}: YAML parse error: {e}")
            continue
            
        # Extract fields
        # Note: We fallback to generic/unknown-env since early versions might not have them
        failure_mode = "generic"
        service = metadata.get("service", "cluster-wide")
        environment = "unknown-env"
        
        failure_slug = _slugify_segment(failure_mode, fallback="generic")
        service_slug = _slugify_segment(service, fallback="cluster-wide")
        env_slug = _slugify_segment(environment, fallback="unknown-env")
        
        base_name = f"{failure_slug}--{service_slug}--{env_slug}"
        new_file_path = RUNBOOKS_DIR / f"{base_name}.md"
        
        if new_file_path == file_path:
            print(f"Skipping {file_path.name}: Already follows convention.")
            continue
            
        # Handle collisions
        suffix = 2
        while new_file_path.exists():
            new_file_path = RUNBOOKS_DIR / f"{base_name}-{suffix}.md"
            suffix += 1
            
        file_path.rename(new_file_path)
        print(f"Migrated: {file_path.name} -> {new_file_path.name}")
        migrated_count += 1
        
    print(f"Migration complete. Renamed {migrated_count} files.")
    print("Please run `uv run python scripts/ingest_knowledge.py` for each migrated file (or manually clear and rebuild the index) to update the vector store.")

if __name__ == "__main__":
    migrate_filenames()
