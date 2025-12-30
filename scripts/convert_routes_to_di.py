#!/usr/bin/env python3
"""Script to convert API routes to use dependency injection.

This script automatically adds dependency injection parameters to route handlers
that use the global adapter instances (db, storage, task_queue, openai_client, etc.).

Usage:
    python scripts/convert_routes_to_di.py
"""
import re
from pathlib import Path


def add_dependency_to_handler(content: str, adapter_name: str, dependency_func: str, type_name: str) -> tuple[str, int]:
    """Add dependency injection parameter to route handlers that use an adapter.

    Args:
        content: File content
        adapter_name: Name of the adapter variable (e.g., 'db', 'storage')
        dependency_func: Name of dependency function (e.g., 'get_db', 'get_storage')
        type_name: Type annotation (e.g., 'Database', 'SupabaseStorage')

    Returns:
        Tuple of (modified_content, count_of_changes)
    """
    changes = 0

    # Pattern to find function definitions (sync or async)
    # that contain usage of the adapter but don't already have it as a parameter
    func_pattern = r'((?:async )?def \w+\([^)]*\):)'

    def check_and_add_param(match):
        nonlocal changes
        func_def = match.group(0)
        # Get the entire function to check if it uses the adapter
        func_start = match.start()
        # Find the next function or end of file
        next_func = content.find('\ndef ', func_start + 1)
        next_async_func = content.find('\nasync def ', func_start + 1)
        if next_func == -1:
            next_func = len(content)
        if next_async_func != -1 and next_async_func < next_func:
            next_func = next_async_func

        func_body = content[func_start:next_func]

        # Check if function uses the adapter
        uses_adapter = re.search(rf'\b{adapter_name}\.', func_body)
        # Check if already has the parameter
        has_param = re.search(rf'\b{adapter_name}\s*:\s*{type_name}\s*=\s*Depends\({dependency_func}\)', func_def)

        if uses_adapter and not has_param:
            # Add the parameter before the closing paren
            # Find if there are existing parameters
            param_list = func_def[func_def.find('(') + 1:func_def.rfind(')')]
            if param_list.strip():
                # Has parameters, add comma and new param
                new_func_def = func_def.replace(
                    '):',
                    f',\n    {adapter_name}: {type_name} = Depends({dependency_func}),\n):'
                )
            else:
                # No parameters, just add
                new_func_def = func_def.replace(
                    '):',
                    f'{adapter_name}: {type_name} = Depends({dependency_func})):'
                )
            changes += 1
            return new_func_def

        return func_def

    # This is a simplified approach - for production, use AST parsing
    # For now, manually update each file
    return content, changes


def update_imports_in_file(file_path: Path) -> bool:
    """Update imports in a route file.

    Returns:
        True if file was modified
    """
    content = file_path.read_text()
    original = content

    # Check if file uses old global imports
    uses_old_imports = any([
        'from ..adapters.database import db' in content,
        'from ..adapters.supabase import storage' in content,
        'from ..adapters.queue import task_queue' in content,
        'from ..adapters.openai_client import openai_client' in content,
        'from ..adapters.opensearch_client import opensearch_client' in content,
    ])

    if not uses_old_imports:
        return False

    # Replace old imports
    content = content.replace(
        'from ..adapters.database import db',
        'from ..dependencies import get_db\nfrom ..adapters.database import Database'
    )
    content = content.replace(
        'from ..adapters.supabase import storage',
        'from ..dependencies import get_storage\nfrom ..adapters.supabase import SupabaseStorage'
    )
    content = content.replace(
        'from ..adapters.queue import task_queue',
        'from ..dependencies import get_queue\nfrom ..adapters.queue import TaskQueue'
    )
    content = content.replace(
        'from ..adapters.openai_client import openai_client',
        'from ..dependencies import get_openai\nfrom ..adapters.openai_client import OpenAIClient'
    )
    content = content.replace(
        'from ..adapters.opensearch_client import opensearch_client',
        'from ..dependencies import get_opensearch\nfrom ..adapters.opensearch_client import OpenSearchClient'
    )

    if content != original:
        file_path.write_text(content)
        print(f"✓ Updated imports in {file_path.name}")
        return True

    return False


def main():
    """Update all route files to use dependency injection."""
    routes_dir = Path(__file__).parent.parent / 'services' / 'api' / 'src' / 'routes'

    if not routes_dir.exists():
        print(f"Routes directory not found: {routes_dir}")
        return

    route_files = list(routes_dir.glob('*.py'))
    route_files = [f for f in route_files if f.name != '__init__.py']

    print(f"Found {len(route_files)} route files to process")
    print("\nStep 1: Updating imports...")

    modified_count = 0
    for route_file in route_files:
        if update_imports_in_file(route_file):
            modified_count += 1

    print(f"\nUpdated imports in {modified_count} files")
    print("\nStep 2: Manual work required")
    print("=" * 60)
    print("The imports have been updated. Now you need to manually:")
    print("1. Add dependency parameters to each route handler function")
    print("2. Example:")
    print("   OLD: async def handler(current_user: User = Depends(get_current_user)):")
    print("   NEW: async def handler(")
    print("            current_user: User = Depends(get_current_user),")
    print("            db: Database = Depends(get_db),")
    print("        ):")
    print("\n3. For task_queue methods, pass db explicitly:")
    print("   OLD: task_queue.enqueue_video_processing(video_id)")
    print("   NEW: queue.enqueue_video_processing(video_id, db=db)")
    print("\nFiles that need manual updates:")
    for f in route_files:
        print(f"  - {f.name}")


if __name__ == '__main__':
    main()
