"""
word_formatter 服务层
"""

from .ast_generator import (
    parse_markdown_to_ast,
    parse_plaintext_heuristic,
    parse_plaintext_with_ai_types,
    ai_identify_paragraph_types,
    identify_paragraph_type,
)
from .spec_generator import (
    build_generic_spec,
    builtin_specs,
    ai_generate_spec,
    validate_custom_spec,
    export_spec_to_json,
    get_spec_schema,
)
from .template_generator import (
    generate_reference_docx,
    patch_reference_docx,
)
from .renderer import (
    render_docx,
    RenderOptions,
)
from .validator import validate_docx
from .fixer import (
    fix_docx,
    build_patch_from_report,
    apply_patch,
)
from .compiler import (
    compile_document,
    compile_document_with_ai,
    CompileOptions,
    CompileResult,
    CompileProgress,
    CompilePhase,
    InputFormat,
    detect_input_format,
)
from .job_manager import (
    JobManager,
    Job,
    JobStatus,
    JobProgress,
    get_job_manager,
    init_job_manager,
)

__all__ = [
    # AST Generator
    "parse_markdown_to_ast",
    "parse_plaintext_heuristic",
    "parse_plaintext_with_ai_types",
    "ai_identify_paragraph_types",
    "identify_paragraph_type",
    # Spec Generator
    "build_generic_spec",
    "builtin_specs",
    "ai_generate_spec",
    "validate_custom_spec",
    "export_spec_to_json",
    "get_spec_schema",
    # Template Generator
    "generate_reference_docx",
    "patch_reference_docx",
    # Renderer
    "render_docx",
    "RenderOptions",
    # Validator
    "validate_docx",
    # Fixer
    "fix_docx",
    "build_patch_from_report",
    "apply_patch",
    # Compiler
    "compile_document",
    "compile_document_with_ai",
    "CompileOptions",
    "CompileResult",
    "CompileProgress",
    "CompilePhase",
    "InputFormat",
    "detect_input_format",
    # Job Manager
    "JobManager",
    "Job",
    "JobStatus",
    "JobProgress",
    "get_job_manager",
    "init_job_manager",
]
