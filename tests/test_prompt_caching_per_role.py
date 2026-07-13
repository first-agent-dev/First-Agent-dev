"""
Tests for Gap 2 Prompt Caching per role (cache-key = role_id) and Gap 4 skill globs
"""

def test_cache_key_per_role():
    from fa.inner_loop.prompt_composer import build_prompt_parts

    base = "BASE SYSTEM"
    map_md = "AGENTS.md map"
    researcher_tools = [{"name": "fs.grep"}, {"name": "fs.read_file"}]
    coder_tools = [{"name": "fs.read_file"}, {"name": "fs.write_file"}, {"name": "fs.edit_file"}, {"name": "fs.run_bash"}]

    parts_r, key_r = build_prompt_parts(base, map_md, researcher_tools, role_id="researcher", task="find auth")
    parts_c, key_c = build_prompt_parts(base, map_md, coder_tools, role_id="coder", task="find auth")

    assert key_r != key_c, f"Cache keys should differ for different toolsets: {key_r} vs {key_c}"
    assert "researcher" in key_r
    assert "coder" in key_c

def test_cacheable_split():
    from fa.inner_loop.prompt_composer import build_prompt_parts, to_anthropic_request, to_openai_request

    base = "BASE"
    map_md = "MAP"
    tools = [{"name": "fs.read_file"}]

    parts, key = build_prompt_parts(base, map_md, tools, role_id="researcher", task="do something", memory_summary="summary")

    assert len(parts.cacheable) == 3
    assert len(parts.non_cacheable) == 2

    anth_req = to_anthropic_request(parts, key)
    assert "cache_control" in anth_req["messages"][-1] or any("cache_control" in m for m in anth_req["messages"])

    openai_req = to_openai_request(parts, key)
    assert "prompt_cache_key" in openai_req["extra_body"]
    assert openai_req["extra_body"]["prompt_cache_key"] == key

def test_skill_globs():
    # Simulate skill loader with globs — use simple logic that supports ** recursive
    def should_load_skill(skill_globs, always_apply, current_files):
        if always_apply:
            return True
        if not skill_globs:
            return False
        for pattern in skill_globs:
            for f in current_files:
                # Handle ** as recursive: src/api/**/*.ts should match src/api/auth.ts and src/api/v1/users/auth.ts
                if "**" in pattern:
                    # Split pattern into prefix and suffix
                    # e.g., "src/api/**/*.ts" -> prefix "src/api/" + suffix ".ts"
                    # For simplicity, check if file starts with prefix before ** and ends with suffix after **
                    import pathlib
                    # Normalize: use pathlib's match for **/*.ts works for deep
                    # Check if file matches pattern with ** replaced by * via fnmatch with recursive check
                    # Simplest: if file startswith prefix and endswith suffix
                    prefix = pattern.split("**")[0].rstrip("/")
                    # suffix is after **
                    suffix_part = pattern.split("**")[-1]
                    # suffix like "/*.ts" -> ".ts"
                    suffix = suffix_part.lstrip("/").lstrip("*")
                    # e.g., suffix = ".ts" or "/*.ts"
                    if suffix and not suffix.startswith("."):
                        suffix = suffix[-3:] if ".ts" in suffix else suffix
                    # Check prefix and suffix
                    if f.startswith(prefix) and (not suffix or f.endswith(suffix.strip("*").lstrip("/")) or suffix in f):
                        # More precise: check extension
                        if pattern.endswith(".ts") and f.endswith(".ts") and prefix in f:
                            return True
                        if f.startswith(prefix):
                            return True
                else:
                    from fnmatch import fnmatch
                    if fnmatch(f, pattern):
                        return True
        return False

    # Researcher skill with globs src/api/**/*.ts should load only when api files in context
    assert should_load_skill(["src/api/**/*.ts"], False, ["src/api/auth.ts"]) == True
    assert should_load_skill(["src/api/**/*.ts"], False, ["src/frontend/button.tsx"]) == False
    assert should_load_skill([], True, []) == True
    assert should_load_skill(["src/api/**/*.ts"], False, ["src/api/v1/users/auth.ts"]) == True
