import os, ast, hashlib, json
from collections import defaultdict

classes = defaultdict(list)

for root, dirs, files in os.walk("."):
    dirs[:] = [d for d in dirs if d not in ["venv", ".git", "node_modules", "__pycache__", "dist", "build", ".audit_tmp"]]
    for f in files:
        if not f.endswith(".py"):
            continue
        fp = os.path.join(root, f)
        try:
            src = open(fp, "r", encoding="utf-8", errors="ignore").read()
            tree = ast.parse(src, filename=fp)
            for node in ast.walk(tree):
                if isinstance(node, ast.ClassDef):
                    lines = src.splitlines()
                    start = node.lineno - 1
                    end = node.end_lineno
                    class_src = "\n".join(lines[start:end])
                    class_hash = hashlib.sha256(class_src.encode()).hexdigest()[:16]
                    file_hash = hashlib.sha256(open(fp, "rb").read()).hexdigest()[:16]
                    classes[node.name].append({
                        "file": fp,
                        "line": node.lineno,
                        "impl_hash": class_hash,
                        "file_hash": file_hash,
                        "methods": [n.name for n in ast.walk(node) if isinstance(n, ast.FunctionDef)]
                    })
        except Exception:
            pass

dup_names = {k: v for k, v in classes.items() if len(v) > 1}

print(f"TOTAL_DUP_NAMES={len(dup_names)}")
print(f"TOTAL_DUP_OCCURRENCES={sum(len(v) for v in dup_names.values())}")
print("---")
for name, locs in sorted(dup_names.items()):
    hashes = [l["impl_hash"] for l in locs]
    all_same = len(set(hashes)) == 1
    print(f"CLASS={name} COUNT={len(locs)} ALL_SAME_IMPL={all_same}")
    for l in locs:
        print(f"  FILE={l['file']} LINE={l['line']} IMPL_HASH={l['impl_hash']} FILE_HASH={l['file_hash']}")

# Save full JSON
with open("artifacts/system_audit/duplicate_forensics/raw_scan.json", "w") as fout:
    json.dump({k: v for k, v in dup_names.items()}, fout, indent=2)
print("SAVED raw_scan.json")
