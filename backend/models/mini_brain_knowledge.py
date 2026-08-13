"""MB-02: Brud Knowledge Core API schemas."""

from pydantic import Field

from backend.core.validation import DomainModel


class KnowledgeItemCreate(DomainModel):
    domain: str = Field(min_length=1, max_length=60)
    title: str = Field(min_length=1, max_length=200)
    category: str = Field(min_length=1, max_length=80)
    description: str = Field(default="", max_length=4000)
    keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    related_features: list[str] = Field(default_factory=list)
    related_apis: list[str] = Field(default_factory=list)
    related_services: list[str] = Field(default_factory=list)
    related_documentation: list[str] = Field(default_factory=list)
    source: str = Field(default="", max_length=400)
    version: str = Field(default="1.0", max_length=20)
    status: str = Field(default="active")


class KnowledgeRelationshipCreate(DomainModel):
    from_public_id: str
    to_public_id: str
    relationship_type: str
    description: str = Field(default="", max_length=1000)
