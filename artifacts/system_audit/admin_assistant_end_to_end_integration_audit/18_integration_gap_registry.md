# 18 INTEGRATION GAP REGISTRY

| ID | Severity | Feature | Current State | Expected State | Root Cause |
|---|---|---|---|---|---|
| GAP-01 | MEDIUM | Chat Tool Execution | Widget calls `/mini-brain/llm-runtime/chat` directly | Widget calls `/admin/assistant/chat` or passes tools | Widget API switch in `api.js` line 784 |
| GAP-02 | LOW | Provider Status in Chat | Provider status viewable on dashboard | Provider status inspectable via chat prompt | Missing tool wrapper in `admin_assistant_tools.py` |
| GAP-03 | LOW | Training Loss Curves in Chat | Training curves viewable on dashboard | Pretraining loss curves inspectable via chat | Missing tool wrapper in `admin_assistant_tools.py` |
