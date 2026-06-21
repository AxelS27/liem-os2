import ast
import os
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("LiemCompressor")

class ContextCompressor:
    """
    Context Compressor and Diff Ingestion Engine.
    Handles Search-and-Replace block matches and AST Node ID code injections.
    """
    def __init__(self):
        pass

    def apply_search_replace(self, file_path: str, search_block: str, replace_block: str) -> bool:
        """Applies exact substring search-and-replace to target file."""
        if not os.path.exists(file_path):
            logger.error(f"[Compressor] Target file {file_path} not found.")
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()

        # Clean carriage returns for consistent matching
        search_clean = search_block.replace("\r\n", "\n").strip()
        content_clean = content.replace("\r\n", "\n")

        if search_clean not in content_clean:
            logger.error(f"[Compressor] Substring match failed for search block in {file_path}.")
            logger.debug(f"Search block:\n{search_clean}")
            return False

        # Execute substitution
        new_content = content_clean.replace(search_clean, replace_block.replace("\r\n", "\n").strip())

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_content)

        logger.info(f"[Compressor] Successfully applied Search-and-Replace block on {file_path}.")
        return True

    def apply_ast_injection(self, file_path: str, ast_node_id: str, replace_block: str) -> bool:
        """
        Locates target function/class using AST parse tree and injects the new body
        at the resolved source code coordinates. Bypasses line offset limitations.
        """
        if not os.path.exists(file_path):
            logger.error(f"[Compressor] Target file {file_path} not found.")
            return False

        with open(file_path, "r", encoding="utf-8") as f:
            source_code = f.read()

        try:
            tree = ast.parse(source_code, filename=file_path)
        except SyntaxError as e:
            logger.error(f"[Compressor] Syntax error in target file {file_path}: {e}")
            return False

        # AST Walker to find target node by ID (e.g. 'calculate_tax' or 'finance_module::calculate_tax')
        target_node = self._find_ast_node(tree, ast_node_id)
        if not target_node:
            logger.error(f"[Compressor] AST Node {ast_node_id} not found in {file_path}.")
            return dict()

        # Resolve coordinates (lineno is 1-indexed)
        lines = source_code.splitlines()
        start_line = target_node.lineno - 1
        end_line = getattr(target_node, "end_lineno", len(lines)) - 1

        # Replace lines in source code
        prefix = "\n".join(lines[:start_line])
        suffix = "\n".join(lines[end_line + 1:])
        
        # Merge parts
        new_code = (prefix + "\n" + replace_block.strip() + "\n" + suffix).strip() + "\n"

        with open(file_path, "w", encoding="utf-8") as f:
            f.write(new_code)

        logger.info(f"[Compressor] Successfully injected code at AST Node '{ast_node_id}' in {file_path}.")
        return True

    def _find_ast_node(self, tree: ast.AST, target_id: str) -> Optional[ast.AST]:
        """Traverses AST looking for a FunctionDef or ClassDef matching the name or path."""
        # Simple match by name first, or split path
        parts = target_id.split("::")
        target_name = parts[-1]

        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                if node.name == target_name:
                    return node
        return None
