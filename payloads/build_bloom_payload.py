import json

with open("context_minimal.json", "r", encoding="utf-8") as f:
    ctx = json.load(f)

payload = {
    "user_project": {
        "title": ctx["user_project"].get("title"),
        "program": ctx["user_project"].get("program"),
        "degree": ctx["user_project"].get("degree"),
        "study_period": ctx["user_project"].get("study_period"),
        "objectives": ctx["user_project"].get("objectives", [])
    },
    "bloom_preanalysis": ctx.get("bloom", {}),
    "conceptual_context": {
        "main_cluster": ctx["semantic_position"]["main_cluster"],
        "keywords_detected": ctx.get("keywords_detected", [])[:10],
        "top_similar_titles": [
            t.get("title")
            for t in ctx.get("top_similar_theses", [])[:5]
        ],
        "temporal_patterns": ctx.get("temporal_patterns", {})
    }
}

with open("ai_bloom_payload.json", "w", encoding="utf-8") as f:
    json.dump(payload, f, ensure_ascii=False, indent=2)

print("Guardado ai_bloom_payload.json")
print("chars:", len(json.dumps(payload, ensure_ascii=False)))