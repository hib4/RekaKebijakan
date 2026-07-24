from __future__ import annotations

import hashlib
import random

GROUPS = ["Pemerintah daerah", "Pelaku usaha", "Warga terdampak", "Akademisi", "Masyarakat sipil", "Media lokal"]
CONCERNS = ["biaya kepatuhan", "akses layanan", "transparansi", "dampak pekerjaan", "kesiapan infrastruktur", "keadilan distribusi"]


def _rng(seed: str) -> random.Random:
    return random.Random(int(hashlib.sha256(seed.encode()).hexdigest()[:16], 16))


def graph(seed: str, title: str, document_names: list[str]) -> dict:
    randomizer = _rng("graph:" + seed)
    nodes = [{"id": "policy", "label": title, "type": "Kebijakan", "summary": "Pokok kebijakan yang dianalisis.", "x": 380, "y": 220}]
    for index, label in enumerate(GROUPS):
        nodes.append({"id": f"stakeholder-{index+1}", "label": label, "type": "Stakeholder", "group": label, "summary": f"Aktor dengan pengaruh {randomizer.uniform(.5, .95):.2f}.", "x": 80 + (index % 3) * 300, "y": 50 + (index // 3) * 340})
    for index, label in enumerate(CONCERNS):
        source = ", ".join(document_names) or "tujuan proyek"
        nodes.append({"id": f"concern-{index+1}", "label": label, "type": "Isu", "summary": f"Isu teridentifikasi dari {source}.", "x": 130 + (index % 3) * 280, "y": 150 + (index // 3) * 180})
    edges = []
    for index in range(6):
        edges.extend([{"id": f"edge-{index*2+1}", "source": f"stakeholder-{index+1}", "target": "policy", "type": "RESPONDS_TO"}, {"id": f"edge-{index*2+2}", "source": f"stakeholder-{index+1}", "target": f"concern-{index+1}", "type": "RAISES"}])
    return {"nodes": nodes, "edges": edges}


def environment(seed: str, config: dict) -> dict:
    randomizer = _rng("environment:" + seed)
    names = ["Rina", "Budi", "Siti", "Arif", "Maya", "Dimas", "Nadia", "Raka", "Lestari", "Fajar"]
    personas = []
    for index in range(30):
        group, concern = GROUPS[index % 6], CONCERNS[index % 6]
        stance = randomizer.choice(["Mendukung", "Netral", "Kritis"])
        personas.append({"id": f"persona-{index+1}", "name": f"{names[index % 10]} {index+1}", "group": group, "stakeholder_group": group, "role": "Persona sintetis", "stance": stance, "concern": concern, "concerns": [concern], "topics": [concern], "count": 1})
    return {"personas": personas, "persona_count": 30, "config": config}


def events(seed: str, rounds: int) -> list[dict]:
    randomizer = _rng("events:" + seed)
    result = []
    for round_number in range(1, rounds + 1):
        for index, group in enumerate(GROUPS):
            concern = CONCERNS[(index + round_number - 1) % 6]
            stance = randomizer.choice(["Mendukung", "Netral", "Kritis"])
            event_id = f"event-r{round_number}-{index+1}"
            statement = f"{group} menyoroti {concern} pada putaran {round_number}."
            result.append({"id": event_id, "round": round_number, "time": f"{round_number-1:02d}:{index*8:02d}", "channel": ["Forum warga", "Media sosial", "Rapat publik"][index % 3], "persona": f"{group} #{index+1}", "persona_name": f"{group} #{index+1}", "group": group, "type": "respons_publik", "event_type": "respons_publik", "statement": statement, "content": statement, "stance": stance, "concerns": [concern], "risk_narrative": "Perlu mitigasi" if stance == "Kritis" else "Terkendali", "influence_source": "Graph kebijakan"})
    return result


def report(title: str, events_list: list[dict], documents: list[dict]) -> dict:
    critical = [event for event in events_list if event["stance"] == "Kritis"]
    citations = [f"[dok:{doc['id']}]" for doc in documents] or ["[event:event-r1-1]"]
    evidence = f"{len(critical)} dari {len(events_list)} event bersikap kritis; sumber {', '.join(citations)} dan [event:event-r1-1]."
    return {"title": f"Laporan Simulasi {title}", "sections": [
        {"id": "ringkasan", "title": "Ringkasan Eksekutif", "paragraphs": [f"Simulasi mencatat {len(events_list)} respons lintas kelompok. {citations[0]}"]},
        {"id": "temuan", "title": "Temuan dan Bukti", "paragraphs": [evidence]},
        {"id": "rekomendasi", "title": "Rekomendasi", "paragraphs": ["Lakukan implementasi bertahap, buka kanal umpan balik, dan ukur akses layanan pada setiap putaran."]},
    ], "risks": [
        {"id": "risk-1", "title": "Resistensi kelompok terdampak", "level": "Tinggi" if len(critical) > len(events_list) / 3 else "Sedang", "trend": "Stabil", "evidence": evidence},
        {"id": "risk-2", "title": "Kesenjangan akses layanan", "level": "Sedang", "trend": "Meningkat", "evidence": "Isu akses berulang pada jejak [event:event-r1-2]."},
    ]}


def answer(tool: str, question: str, group: str | None, state: dict) -> dict:
    events_list = state["simulation"].get("events", [])
    selected = [event for event in events_list if not group or event["group"] == group]
    citation = f"event:{selected[0]['id']}" if selected else "report:ringkasan"
    prefix = {
        "persona": "Perspektif persona",
        "evidence": "Bukti simulasi",
        "risk": "Analisis risiko",
        "report": "Laporan",
        "compare": "Perbandingan skenario",
        "revision": "Catatan revisi",
    }[tool]
    text = f"{prefix}: berdasarkan {len(selected)} event relevan, pertanyaan '{question}' perlu dijawab dengan mitigasi bertahap dan komunikasi terbuka. [{citation}]"
    return {"text": text, "citations": [citation]}
