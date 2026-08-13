"""MB-15: Vision Model Integration & Human-in-the-Loop Annotation
Center -- pure decision logic only, zero I/O.

MB-15 is not another Vision Intelligence module (that is MB-14, whose
own tables/images/objects this phase only ever reads). MB-15 connects
a real, pluggable vision inference backend (see `backend.services.
vision_inference_backend`) to MB-14's already-extracted images, and
structures whatever that backend predicts into suggestions an admin
must review before anything is trusted.

No vision model file exists anywhere in this environment (confirmed
by audit), so every module here is written and tested against real,
honest "provider unavailable" inputs as well as hand-constructed
"what a real prediction would look like" fixtures -- never against an
actual loaded model. `relationship_detector.py` does not implement its
own geometry: it re-exports MB-14's own already-tested `core_model.
mini_brain.vision_intelligence.knowledge_graph_builder.
build_knowledge_graph`, since a relationship between two objects is
the same bounding-box geometry problem whether the boxes came from an
admin (MB-14) or a vision provider (MB-15).
"""
