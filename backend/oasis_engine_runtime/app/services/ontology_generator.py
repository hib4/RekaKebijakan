"""
Ontology generation service.
API 1: Analyze text and generate entity and relationship type definitions for social simulation.
"""

import json
import logging
import re
from typing import Dict, Any, List, Optional
from ..utils.llm_client import LLMClient
from ..utils.file_parser import split_text_into_chunks
from ..utils.locale import get_language_instruction, t
from ..utils.ontology import (
    MAX_ONTOLOGY_TYPES,
    normalize_ontology_attributes,
    normalize_ontology_source_targets,
)

logger = logging.getLogger(__name__)


def _to_pascal_case(name: str) -> str:
    """Convert a name in any format to PascalCase."""
    # Split on non-alphanumeric characters.
    parts = re.split(r'[^a-zA-Z0-9]+', name)
    # Then split on camelCase boundaries.
    words = []
    for part in parts:
        words.extend(re.sub(r'([a-z])([A-Z])', r'\1_\2', part).split('_'))
    # Capitalize each non-empty word.
    result = ''.join(word.capitalize() for word in words if word)
    return result if result else 'Unknown'


def _to_upper_snake_case(name: str) -> str:
    """Convert free-form or camelCase names to SCREAMING_SNAKE_CASE."""

    separated = re.sub(r'([a-z0-9])([A-Z])', r'\1_\2', name.strip())
    normalized = re.sub(r'[^a-zA-Z0-9]+', '_', separated).strip('_').upper()
    if not normalized:
        return "UNKNOWN"
    if normalized[0].isdigit():
        normalized = f"REL_{normalized}"
    return normalized


# Ontology-generation system prompt.
ONTOLOGY_SYSTEM_PROMPT = """You are an expert knowledge-graph ontology designer. Analyze the supplied text and simulation requirements, then design entity and relationship types suitable for **social-media public-opinion simulation**.

**Important: Return valid JSON only. Do not output anything else.**

## Core context

We are building a **social-media public-opinion simulation system**. In this system:
- Each entity is an account or actor that can speak, interact, and spread information on social media.
- Entities influence one another, repost, comment, and respond.
- We simulate how participants react to public events and how information spreads.

Therefore, **entities must be real-world actors capable of speaking and interacting on social media**.

**Allowed entities include:**
- Specific people, such as public figures, involved parties, opinion leaders, experts, academics, and ordinary people.
- Companies and businesses, including official accounts.
- Organizations such as universities, associations, NGOs, and unions.
- Government departments and regulators.
- Media outlets such as newspapers, broadcasters, independent media, and websites.
- Social-media platforms.
- Representatives of specific groups, such as alumni groups, fan groups, and advocacy groups.

**Disallowed entities include:**
- Abstract concepts such as public opinion, sentiment, or trends.
- Topics such as academic integrity or education reform.
- Viewpoints or attitudes such as supporters or opponents.

## Output format

Return JSON with this structure:

```json
{
    "entity_types": [
        {
            "name": "Entity type name in English PascalCase",
            "description": "Brief natural-language description, no more than 100 characters",
            "attributes": [
                {
                    "name": "English attribute name in snake_case",
                    "type": "text",
                    "description": "Attribute description"
                }
            ],
            "examples": ["Example entity 1", "Example entity 2"]
        }
    ],
    "edge_types": [
        {
            "name": "Relationship type name in English UPPER_SNAKE_CASE",
            "description": "Brief natural-language description, no more than 100 characters",
            "source_targets": [
                {"source": "Source entity type", "target": "Target entity type"}
            ],
            "attributes": []
        }
    ],
    "analysis_summary": "Brief analysis of the text"
}
```

## Design guidelines (critical)

### 1. Entity type design

**Quantity: define exactly 10 entity types.**

The 10 types must include both specific and fallback types:

A. **Fallback types, required as the final two entries:**
   - `Person`: Fallback for any individual who does not fit a more specific person type.
   - `Organization`: Fallback for any organization that does not fit a more specific organization type.

B. **Eight specific types derived from the text:**
   - Design specific types for the main actors in the text.
   - Academic events might use `Student`, `Professor`, and `University`.
   - Business events might use `Company`, `CEO`, and `Employee`.

Fallback types are needed because the text may mention people such as schoolteachers, passersby, or anonymous users. If no specific type matches, use `Person`. Likewise, use `Organization` for small organizations and temporary groups.

Specific types must represent frequent or important actor roles, have clear non-overlapping boundaries, and use descriptions that distinguish them from fallback types.

### 2. Relationship type design

- Define 6-10 relationship types.
- Relationships should represent genuine social-media interactions or real-world connections.
- Ensure `source_targets` cover the entity types you define.

### 3. Attribute design

- Define 1-3 important attributes per entity type.
- Do not use reserved attribute names: `name`, `uuid`, `group_id`, `graph_id`, `created_at`, or `summary`.
- Prefer names such as `full_name`, `title`, `role`, `position`, `location`, and `description`.

## Entity type examples

Specific person types: `Student`, `Professor`, `Journalist`, `Celebrity`, `Executive`, `Official`, `Lawyer`, `Doctor`.
Person fallback: `Person`.
Specific organization types: `University`, `Company`, `GovernmentAgency`, `MediaOutlet`, `Hospital`, `School`, `NGO`.
Organization fallback: `Organization`.

## Relationship type examples

`WORKS_FOR`, `STUDIES_AT`, `AFFILIATED_WITH`, `REPRESENTS`, `REGULATES`, `REPORTS_ON`, `COMMENTS_ON`, `RESPONDS_TO`, `SUPPORTS`, `OPPOSES`, `COLLABORATES_WITH`, `COMPETES_WITH`.
"""


class OntologyGenerator:
    """
    Analyze text and generate ontology entity and relationship definitions.
    """
    
    def __init__(self, llm_client: Optional[LLMClient] = None):
        self.llm_client = llm_client or LLMClient()
    
    def generate(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate an ontology definition.
        
        Args:
            document_texts: Document text list.
            simulation_requirement: Simulation requirement description.
            additional_context: Additional context.
            
        Returns:
            Ontology definition containing entity_types, edge_types, and related fields.
        """
        # Build the user message.
        user_message = self._build_user_message(
            document_texts, 
            simulation_requirement,
            additional_context
        )
        
        system_prompt = (
            f"{ONTOLOGY_SYSTEM_PROMPT}\n\n{get_language_instruction()} "
            "Descriptions, examples, and analysis_summary are natural-language content. "
            "Entity type names MUST remain English PascalCase (e.g., 'PersonEntity', "
            "'MediaOrganization'). Relationship type names MUST remain English "
            "UPPER_SNAKE_CASE (e.g., 'WORKS_FOR'). Attribute names MUST remain English snake_case."
        )
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ]
        
        # Call the LLM.
        result = self.llm_client.chat_json(
            messages=messages,
            temperature=0.3,
            # Structured ontology responses can exceed 4096 completion tokens,
            # especially when a compatible provider counts hidden reasoning in
            # the same budget. Let the provider use its model-specific limit.
            max_tokens=None,
            max_attempts=2,
        )
        
        # Validate and post-process the result.
        result = self._validate_and_process(result)
        
        return result
    
    # Maximum text length sent to the LLM.
    MAX_TEXT_LENGTH_FOR_LLM = 50000
    LONG_TEXT_CHUNK_SIZE = 8000
    LONG_TEXT_CHUNK_OVERLAP = 200
    MAX_LONG_TEXT_CHUNKS = 60
    MIN_LONG_TEXT_EXCERPT = 400
    
    def _build_user_message(
        self,
        document_texts: List[str],
        simulation_requirement: str,
        additional_context: Optional[str]
    ) -> str:
        """Build the user message."""
        
        combined_text = self._build_document_context(document_texts)
        
        message = f"""## Simulation requirement

{simulation_requirement}

## Document content

{combined_text}
"""
        
        if additional_context:
            message += f"""
## Additional context

{additional_context}
"""
        
        message += """
Design entity and relationship types suitable for public-opinion simulation from the content above.

**Required rules:**
1. Return exactly 10 entity types.
2. The final two must be the fallback types `Person` and `Organization`.
3. The first eight must be specific types derived from the text.
4. Every entity type must be a real-world actor capable of speaking, not an abstract concept.
5. Do not use reserved attributes such as `name`, `uuid`, `group_id`, or `graph_id`; use alternatives such as `full_name` and `org_name`.
"""
        
        return message

    def _build_document_context(self, document_texts: List[str]) -> str:
        """Build document context using representative chunks for long text."""

        combined_text = "\n\n---\n\n".join(document_texts)
        original_length = len(combined_text)

        if original_length <= self.MAX_TEXT_LENGTH_FOR_LLM:
            return combined_text

        chunks = self._collect_document_chunks(document_texts)
        if not chunks:
            return ""

        selected_chunks = self._select_representative_chunks(chunks)
        excerpt_budget = self._calculate_excerpt_budget(len(selected_chunks))
        context = self._render_chunked_context(
            selected_chunks=selected_chunks,
            original_length=original_length,
            total_chunks=len(chunks),
            excerpt_limit=excerpt_budget,
        )

        while len(context) > self.MAX_TEXT_LENGTH_FOR_LLM and excerpt_budget > self.MIN_LONG_TEXT_EXCERPT:
            excerpt_budget = max(self.MIN_LONG_TEXT_EXCERPT, int(excerpt_budget * 0.85))
            context = self._render_chunked_context(
                selected_chunks=selected_chunks,
                original_length=original_length,
                total_chunks=len(chunks),
                excerpt_limit=excerpt_budget,
            )

        if len(context) > self.MAX_TEXT_LENGTH_FOR_LLM:
            marker = "\n\n...(Chunked context compressed to fit the ontology analysis limit)..."
            context = context[:self.MAX_TEXT_LENGTH_FOR_LLM - len(marker)] + marker

        return context

    def _collect_document_chunks(self, document_texts: List[str]) -> List[Dict[str, Any]]:
        """Collect numbered chunks by document for prompt references."""

        all_chunks: List[Dict[str, Any]] = []
        for doc_index, text in enumerate(document_texts, 1):
            doc_chunks = split_text_into_chunks(
                text,
                chunk_size=self.LONG_TEXT_CHUNK_SIZE,
                overlap=self.LONG_TEXT_CHUNK_OVERLAP,
            )
            total_doc_chunks = len(doc_chunks)
            for chunk_index, chunk in enumerate(doc_chunks, 1):
                all_chunks.append({
                    "document_index": doc_index,
                    "chunk_index": chunk_index,
                    "total_document_chunks": total_doc_chunks,
                    "text": chunk,
                })

        return all_chunks

    def _select_representative_chunks(self, chunks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sample chunks evenly across the beginning, middle, and end."""

        if len(chunks) <= self.MAX_LONG_TEXT_CHUNKS:
            return chunks

        if self.MAX_LONG_TEXT_CHUNKS <= 1:
            return [chunks[0]]

        last_index = len(chunks) - 1
        selected_indexes = {
            round(i * last_index / (self.MAX_LONG_TEXT_CHUNKS - 1))
            for i in range(self.MAX_LONG_TEXT_CHUNKS)
        }
        return [chunks[i] for i in sorted(selected_indexes)]

    def _calculate_excerpt_budget(self, selected_count: int) -> int:
        """Allocate a character budget per selected chunk."""

        header_budget = 600
        chunk_header_budget = 120 * selected_count
        available = max(
            self.MIN_LONG_TEXT_EXCERPT * selected_count,
            self.MAX_TEXT_LENGTH_FOR_LLM - header_budget - chunk_header_budget,
        )
        return max(self.MIN_LONG_TEXT_EXCERPT, available // max(selected_count, 1))

    def _render_chunked_context(
        self,
        selected_chunks: List[Dict[str, Any]],
        original_length: int,
        total_chunks: int,
        excerpt_limit: int,
    ) -> str:
        """Render chunked context for long text."""

        lines = [
            (
                f"[Automatic long-text chunk summary] The source has {original_length} characters "
                f"and was divided into {total_chunks} chunks for full-document coverage."
            ),
            (
                f"The following excerpts show {len(selected_chunks)} representative chunks "
                "from the beginning, middle, and end. Design the ontology from evidence across "
                "the document rather than relying only on its opening."
            ),
        ]

        for chunk in selected_chunks:
            excerpt = self._excerpt_text(chunk["text"], excerpt_limit)
            lines.append(
                "\n".join([
                    (
                        f"--- Document {chunk['document_index']} / "
                        f"Chunk {chunk['chunk_index']}/{chunk['total_document_chunks']} ---"
                    ),
                    excerpt,
                ])
            )

        return "\n\n".join(lines)

    @staticmethod
    def _excerpt_text(text: str, char_limit: int) -> str:
        """Keep both ends of a long chunk instead of retaining only its opening."""

        text = text.strip()
        if len(text) <= char_limit:
            return text

        marker = "\n...(Middle of this chunk omitted)...\n"
        if char_limit <= len(marker) + 20:
            return text[:char_limit]

        remaining = char_limit - len(marker)
        head_len = remaining // 2
        tail_len = remaining - head_len
        return f"{text[:head_len].rstrip()}{marker}{text[-tail_len:].lstrip()}"
    
    def _validate_and_process(self, result: Dict[str, Any]) -> Dict[str, Any]:
        """Validate and post-process the result."""
        if not isinstance(result, dict):
            raise ValueError("Ontology result must be an object")

        raw_entities = result.get("entity_types")
        raw_edges = result.get("edge_types")
        if not isinstance(raw_entities, list):
            raw_entities = []
        if not isinstance(raw_edges, list):
            raw_edges = []
        if not isinstance(result.get("analysis_summary"), str):
            result["analysis_summary"] = ""

        # Normalize entity entries before touching their fields. LLMs
        # occasionally emit a bare string, null, or another scalar.
        entity_name_map: Dict[str, str] = {}
        processed_entities: List[Dict[str, Any]] = []
        seen_entity_names = set()
        for raw_entity in raw_entities:
            if isinstance(raw_entity, str):
                entity = {"name": raw_entity}
            elif isinstance(raw_entity, dict):
                entity = dict(raw_entity)
            else:
                logger.warning("Ignoring non-object ontology entity entry")
                continue

            original_name = entity.get("name")
            if not isinstance(original_name, str) or not original_name.strip():
                logger.warning("Ignoring ontology entity without a usable name")
                continue
            original_name = original_name.strip()
            normalized_name = _to_pascal_case(original_name)
            if normalized_name == "Unknown":
                continue
            if normalized_name in seen_entity_names:
                logger.warning(f"Duplicate entity type '{normalized_name}' removed during validation")
                entity_name_map[original_name] = normalized_name
                entity_name_map[original_name.lower()] = normalized_name
                continue

            if normalized_name != original_name:
                logger.warning(
                    f"Entity type name '{original_name}' auto-converted to '{normalized_name}'"
                )
            entity["name"] = normalized_name
            entity["attributes"] = normalize_ontology_attributes(
                entity.get("attributes", [])
            )
            if not isinstance(entity.get("examples"), list):
                entity["examples"] = []
            description = entity.get("description")
            if not isinstance(description, str) or not description:
                description = t('generated.ontologyEntityDescription', name=normalized_name)
            entity["description"] = (
                description[:97] + "..." if len(description) > 100 else description
            )

            seen_entity_names.add(normalized_name)
            processed_entities.append(entity)
            entity_name_map[original_name] = normalized_name
            entity_name_map[original_name.lower()] = normalized_name
            entity_name_map[normalized_name] = normalized_name
            entity_name_map[normalized_name.lower()] = normalized_name

        result["entity_types"] = processed_entities

        # Fallback type definitions.
        person_fallback = {
            "name": "Person",
            "description": t('generated.personFallbackDescription'),
            "attributes": [
                {"name": "full_name", "type": "text", "description": t('generated.fullNameDescription')},
                {"name": "role", "type": "text", "description": t('generated.roleDescription')}
            ],
            "examples": [t('generated.ordinaryCitizen'), t('generated.anonymousNetizen')]
        }
        
        organization_fallback = {
            "name": "Organization",
            "description": t('generated.organizationFallbackDescription'),
            "attributes": [
                {"name": "org_name", "type": "text", "description": t('generated.organizationNameDescription')},
                {"name": "org_type", "type": "text", "description": t('generated.organizationTypeDescription')}
            ],
            "examples": [t('generated.smallBusiness'), t('generated.communityGroup')]
        }
        
        # Check for existing fallback types.
        entity_names = {e["name"] for e in result["entity_types"]}
        has_person = "Person" in entity_names
        has_organization = "Organization" in entity_names
        
        # Determine which fallback types must be added.
        fallbacks_to_add = []
        if not has_person:
            fallbacks_to_add.append(person_fallback)
        if not has_organization:
            fallbacks_to_add.append(organization_fallback)
        
        if fallbacks_to_add:
            current_count = len(result["entity_types"])
            needed_slots = len(fallbacks_to_add)
            
            # Remove existing types if adding fallbacks would exceed the limit.
            if current_count + needed_slots > MAX_ONTOLOGY_TYPES:
                # Calculate how many types to remove.
                to_remove = current_count + needed_slots - MAX_ONTOLOGY_TYPES
                # Remove from the end to retain higher-priority specific types.
                result["entity_types"] = result["entity_types"][:-to_remove]
            
            # Add fallback types.
            result["entity_types"].extend(fallbacks_to_add)
        
        # Defensively enforce the final limit.
        result["entity_types"] = result["entity_types"][:MAX_ONTOLOGY_TYPES]

        # Resolve edge endpoints only after entity fallback/capping, so an edge
        # cannot refer to a type that was removed to satisfy Zep's limits.
        valid_entity_names = {entity["name"] for entity in result["entity_types"]}
        for name in valid_entity_names:
            entity_name_map[name] = name
            entity_name_map[name.lower()] = name

        def resolve_entity_name(value: str) -> Optional[str]:
            stripped = value.strip()
            if stripped == "Entity":
                return stripped
            mapped = entity_name_map.get(stripped) or entity_name_map.get(stripped.lower())
            if mapped in valid_entity_names:
                return mapped
            pascal_name = _to_pascal_case(stripped)
            return pascal_name if pascal_name in valid_entity_names else None

        processed_edges: List[Dict[str, Any]] = []
        seen_edge_names = set()
        for raw_edge in raw_edges:
            if isinstance(raw_edge, str):
                # A bare edge name has no endpoints and cannot be installed in
                # Zep safely. Ignore it instead of inventing a relationship.
                logger.warning(f"Ignoring ontology edge without source_targets: {raw_edge}")
                continue
            elif isinstance(raw_edge, dict):
                edge = dict(raw_edge)
            else:
                logger.warning("Ignoring non-object ontology edge entry")
                continue

            original_name = edge.get("name")
            if not isinstance(original_name, str) or not original_name.strip():
                logger.warning("Ignoring ontology edge without a usable name")
                continue
            normalized_name = _to_upper_snake_case(original_name)
            if normalized_name == "UNKNOWN" or normalized_name in seen_edge_names:
                if normalized_name in seen_edge_names:
                    logger.warning(f"Duplicate edge type '{normalized_name}' removed during validation")
                continue
            if normalized_name != original_name:
                logger.warning(
                    f"Edge type name '{original_name}' auto-converted to '{normalized_name}'"
                )
            edge["name"] = normalized_name

            normalized_targets = []
            for source_target in normalize_ontology_source_targets(
                edge.get("source_targets", []),
                limit=None,
            ):
                source = resolve_entity_name(source_target["source"])
                target = resolve_entity_name(source_target["target"])
                if source and target:
                    normalized_targets.append({"source": source, "target": target})
            edge["source_targets"] = normalize_ontology_source_targets(
                normalized_targets
            )
            edge["attributes"] = normalize_ontology_attributes(
                edge.get("attributes", [])
            )
            description = edge.get("description")
            if not isinstance(description, str) or not description:
                description = t('generated.ontologyRelationshipDescription', name=normalized_name)
            edge["description"] = (
                description[:97] + "..." if len(description) > 100 else description
            )

            seen_edge_names.add(normalized_name)
            processed_edges.append(edge)
            if len(processed_edges) == MAX_ONTOLOGY_TYPES:
                break

        result["edge_types"] = processed_edges
        
        return result
    
    def generate_python_code(self, ontology: Dict[str, Any]) -> str:
        """
        Convert an ontology definition to Python code similar to ontology.py.
        
        Args:
            ontology: Ontology definition.
            
        Returns:
            Python code string.
        """
        code_lines = [
            '"""',
            'Custom entity type definitions',
            'Automatically generated by rekakebijakan for public-opinion simulation',
            '"""',
            '',
            'from pydantic import Field',
            'from zep_cloud.external_clients.ontology import EntityModel, EntityText, EdgeModel',
            '',
            '',
            '# ============== Entity type definitions ==============',
            '',
        ]
        
        # Generate entity types.
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            desc = entity.get("description", f"A {name} entity.")
            
            code_lines.append(f'class {name}(EntityModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = entity.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        code_lines.append('# ============== Relationship type definitions ==============')
        code_lines.append('')
        
        # Generate relationship types.
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            # Convert to a PascalCase class name.
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            desc = edge.get("description", f"A {name} relationship.")
            
            code_lines.append(f'class {class_name}(EdgeModel):')
            code_lines.append(f'    """{desc}"""')
            
            attrs = edge.get("attributes", [])
            if attrs:
                for attr in attrs:
                    attr_name = attr["name"]
                    attr_desc = attr.get("description", attr_name)
                    code_lines.append(f'    {attr_name}: EntityText = Field(')
                    code_lines.append(f'        description="{attr_desc}",')
                    code_lines.append(f'        default=None')
                    code_lines.append(f'    )')
            else:
                code_lines.append('    pass')
            
            code_lines.append('')
            code_lines.append('')
        
        # Generate type dictionaries.
        code_lines.append('# ============== Type configuration ==============')
        code_lines.append('')
        code_lines.append('ENTITY_TYPES = {')
        for entity in ontology.get("entity_types", []):
            name = entity["name"]
            code_lines.append(f'    "{name}": {name},')
        code_lines.append('}')
        code_lines.append('')
        code_lines.append('EDGE_TYPES = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            class_name = ''.join(word.capitalize() for word in name.split('_'))
            code_lines.append(f'    "{name}": {class_name},')
        code_lines.append('}')
        code_lines.append('')
        
        # Generate the edge source_targets mapping.
        code_lines.append('EDGE_SOURCE_TARGETS = {')
        for edge in ontology.get("edge_types", []):
            name = edge["name"]
            source_targets = edge.get("source_targets", [])
            if source_targets:
                st_list = ', '.join([
                    f'{{"source": "{st.get("source", "Entity")}", "target": "{st.get("target", "Entity")}"}}'
                    for st in source_targets
                ])
                code_lines.append(f'    "{name}": [{st_list}],')
        code_lines.append('}')
        
        return '\n'.join(code_lines)
