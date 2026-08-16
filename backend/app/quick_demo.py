from __future__ import annotations

import hashlib
from typing import Any

from .provider_contracts import ReportOutput


QUICK_DEMO_BUNDLE_ID = "makan-bergizi-gratis-v1"
QUICK_DEMO_BUNDLE_TITLE = "Makan Bergizi Gratis (MBG)"
QUICK_DEMO_SOURCE = """
Badan Gizi Nasional menyelenggarakan Program Makan Bergizi Gratis (MBG) melalui
Satuan Pelayanan Pemenuhan Gizi (SPPG), sekolah, pemerintah daerah, penyedia
pangan, tenaga kesehatan, dan mekanisme pengawasan publik. Program diarahkan
untuk memperbaiki pemenuhan gizi peserta didik dan kelompok sasaran, tetapi
desain skala nasionalnya memunculkan pertanyaan serius mengenai kesiapan tata
kelola, pembiayaan, pengadaan, dan dampak nyata dibanding biaya peluangnya.

Desain kebijakan MBG perlu menjawab lima kritik utama sebelum ekspansi
dipercepat: apakah sasaran penerima manfaat cukup tepat dan tidak menyingkirkan
kelompok prioritas, apakah peran pusat-daerah realistis, apakah kapasitas SPPG
dan rantai pasok tidak dipaksakan melampaui kesiapan wilayah, apakah pembiayaan
dan pengadaan bebas dari konflik kepentingan, serta apakah indikator dampaknya
lebih kuat daripada sekadar jumlah porsi tersalurkan.

Simulasi ini meninjau rancangan tata kelola nasional MBG sebagai policy review
yang kritis. Kelompok pelaksana pusat, pemerintah daerah, sekolah, SPPG dan
pemasok lokal, tenaga kesehatan/gizi, serta masyarakat sipil/media menguji
argumen untuk menahan ekspansi, memperketat prasyarat, dan mengalihkan sebagian
anggaran bila bukti dampak serta kesiapan implementasi belum memadai.
""".strip()

GROUP_PROFILES = {
    "BGN dan pelaksana pusat": {
        "names": ["Ratna Prameswari", "Dedi Kurniawan", "Nina Ardianti", "Agus Santoso", "Farah Maulida"],
        "role": "Koordinator kebijakan gizi nasional",
        "concern": "Tekanan ekspansi dan pembuktian dampak kebijakan",
        "topics": ["tekanan ekspansi", "bukti dampak", "akuntabilitas nasional"],
    },
    "Pemerintah daerah": {
        "names": ["Sari Wulandari", "Bambang Riyadi", "Nur Aini", "Hendra Gunawan", "Lilis Setiawati"],
        "role": "Koordinator pelaksanaan dan pengawasan daerah",
        "concern": "Mandat pelaksanaan yang tidak sebanding dengan kapasitas dan anggaran daerah",
        "topics": ["beban daerah", "kesiapan wilayah", "mandat tanpa sumber daya"],
    },
    "Sekolah": {
        "names": ["Yuni Hartati", "Rizal Akbar", "Murniati", "Taufik Hidayat", "Dewi Lestari"],
        "role": "Satuan layanan penerima dan pencatat pelaksanaan",
        "concern": "Beban administratif sekolah dan gangguan terhadap fungsi pembelajaran",
        "topics": ["beban sekolah", "data siswa", "waktu pembelajaran"],
    },
    "SPPG dan pemasok lokal": {
        "names": ["Dr. Maya Kusuma", "Rafi Pradana", "Intan Permata", "Bagus Wicaksono", "Rina Oktaviani"],
        "role": "Pelaksana produksi makanan dan rantai pasok lokal",
        "concern": "Risiko pengadaan tergesa-gesa, pembayaran terlambat, dan konsentrasi pemasok",
        "topics": ["risiko pengadaan", "pembayaran", "konsentrasi pemasok"],
    },
    "Tenaga kesehatan dan gizi": {
        "names": ["Alya Ramadhani", "Fikri Anwar", "Siska Melati", "Joko Saputra", "Nadia Putri"],
        "role": "Pemantau kesehatan dan kecukupan gizi",
        "concern": "Lemahnya bukti dampak gizi dan risiko program berhenti pada logistik makanan",
        "topics": ["bukti dampak", "gizi sasaran", "biaya peluang kesehatan"],
    },
    "Masyarakat sipil dan media": {
        "names": ["Andi Prasetyo", "Mega Puspita", "Reza Firmansyah", "Tari Anggraini", "Ilham Nugraha"],
        "role": "Pemantau akuntabilitas layanan publik",
        "concern": "Transparansi anggaran, konflik kepentingan, dan biaya peluang program publik lain",
        "topics": ["anggaran", "konflik kepentingan", "biaya peluang"],
    },
}

ROUND_THEMES = [
    "Pembacaan kritis tujuan dan asumsi kebijakan",
    "Uji risiko salah sasaran dan beban pelaksana",
    "Uji kapasitas, pengadaan, dan biaya peluang",
    "Tekanan atas pengawasan dan bukti dampak",
    "Rekomendasi penahanan ekspansi dan revisi desain",
]

STATEMENTS = [
    [
        "Tujuan gizi MBG penting, tetapi desain saat ini terlalu bergantung pada asumsi bahwa skala besar otomatis menghasilkan dampak.",
        "Daerah khawatir mandat pelaksanaan turun lebih cepat daripada dukungan anggaran, data, dan kapasitas pengawasan.",
        "Sekolah menilai pendataan dan pelaporan MBG berisiko mengalihkan waktu dari fungsi utama pembelajaran.",
        "SPPG dan pemasok lokal melihat risiko pengadaan tergesa-gesa yang dapat mengunci pasar pada pemasok besar.",
        "Tanpa indikator dampak gizi yang kuat, program bisa berhenti sebagai operasi logistik mahal, bukan intervensi kesehatan.",
        "Publik mempertanyakan apakah anggaran sebesar ini lebih efektif dibanding penguatan layanan gizi, sanitasi, dan sekolah yang sudah ada.",
    ],
    [
        "Koreksi data yang disiapkan BGN belum menjawab risiko exclusion error bagi anak rentan di sekolah kecil dan wilayah sulit akses.",
        "Daerah menolak dijadikan penanggung jawab lapangan jika daftar sasaran, anggaran operasional, dan kewenangan koreksi tetap terpusat.",
        "Sekolah membutuhkan kanal koreksi, tetapi juga menolak beban administrasi tambahan tanpa tenaga dan sistem khusus.",
        "SPPG menilai fluktuasi jumlah penerima dapat menghasilkan pemborosan, tekanan pembayaran, dan kompromi mutu bahan.",
        "Tenaga gizi memperingatkan sasaran prioritas bisa tersamar dalam angka cakupan nasional yang terlihat besar.",
        "Media menilai narasi skala nasional menutupi pertanyaan dasar: siapa yang tidak menerima, siapa yang mengawasi, dan siapa yang diuntungkan.",
    ],
    [
        "Pemantauan kapasitas yang diusulkan BGN datang terlambat jika target ekspansi sudah ditetapkan sebelum wilayah diuji.",
        "Daerah meminta ekspansi dihentikan di wilayah yang belum memiliki peta kapasitas dapur, distribusi, dan pengawasan.",
        "Sekolah menilai kesiapan infrastruktur penerimaan makanan tidak boleh diasumsikan hanya karena jumlah siswa tersedia.",
        "Pemasok lokal khawatir aturan pengadaan yang tidak transparan akan mendorong konsentrasi kontrak dan konflik kepentingan.",
        "Tenaga gizi menilai standar menu nasional berisiko mengabaikan kebutuhan lokal, alergi, dan variasi gizi sasaran.",
        "Diskusi publik bergeser ke pertanyaan lebih keras: apakah kapasitas diciptakan secara nyata atau hanya dikejar untuk memenuhi target politik.",
    ],
    [
        "Panel evaluasi BGN belum cukup jika indikator output tetap lebih dominan daripada bukti dampak gizi dan biaya peluang.",
        "Daerah meminta hasil evaluasi mengikat keputusan ekspansi; wilayah yang gagal prasyarat harus ditunda, bukan diberi target baru.",
        "Sekolah menolak pelaporan yang hanya memindahkan risiko administratif dari pusat ke satuan pendidikan.",
        "SPPG meminta audit pengadaan dilakukan sebelum kontrak diperluas karena koreksi setelah kontrak berjalan sering terlambat.",
        "Tenaga gizi menilai program harus berani membuktikan dampak dibanding intervensi alternatif seperti suplementasi, sanitasi, atau edukasi gizi.",
        "Masyarakat sipil meminta dashboard publik yang membuka anggaran, penerima kontrak, keluhan, hasil audit, dan wilayah yang ditunda.",
    ],
    [
        "Review kebijakan merekomendasikan penahanan ekspansi nasional sampai validitas data, kapasitas wilayah, dan audit pengadaan memenuhi ambang minimum.",
        "Daerah hanya siap mendukung jika kewenangan koreksi, pendanaan operasional, dan hak menunda pelaksanaan wilayah dibuat eksplisit.",
        "Sekolah meminta tugas administrasi MBG tidak dijalankan tanpa tenaga tambahan, sistem pelaporan, dan batas beban kerja yang jelas.",
        "SPPG dan pemasok lokal meminta kontrak baru ditunda di wilayah yang belum memiliki kepastian pembayaran dan aturan pengadaan terbuka.",
        "Tenaga gizi meminta pilot dampak yang independen sebelum klaim keberhasilan dipakai untuk membenarkan perluasan anggaran.",
        "Percakapan bergeser dari koreksi teknis menuju argumen kontra: ekspansi cepat berisiko mengubah tujuan gizi menjadi proyek logistik mahal.",
    ],
]

ACTION_TYPES = [
    ["CREATE_POST", "SEARCH_POSTS", "CREATE_COMMENT", "CREATE_POST", "QUOTE_POST", "CREATE_POST"],
    ["CREATE_POST", "CREATE_POST", "CREATE_COMMENT", "QUOTE_POST", "CREATE_POST", "REPOST"],
    ["REPOST", "CREATE_POST", "QUOTE_POST", "CREATE_COMMENT", "CREATE_POST", "SEARCH_POSTS"],
    ["CREATE_POST", "CREATE_COMMENT", "UPVOTE_POST", "CREATE_POST", "QUOTE_POST", "CREATE_POST"],
    ["CREATE_POST", "CREATE_POST", "CREATE_COMMENT", "UPVOTE_POST", "CREATE_POST", "REPOST"],
]

STANCES = [
    ["Netral", "Kritis", "Kritis", "Kritis", "Kritis", "Kritis"],
    ["Netral", "Kritis", "Kritis", "Kritis", "Kritis", "Kritis"],
    ["Kritis", "Kritis", "Kritis", "Kritis", "Kritis", "Kritis"],
    ["Netral", "Kritis", "Kritis", "Kritis", "Kritis", "Kritis"],
    ["Kritis", "Kritis", "Kritis", "Kritis", "Kritis", "Kritis"],
]


def bundle_metadata() -> dict[str, Any]:
    return {
        "id": QUICK_DEMO_BUNDLE_ID,
        "title": QUICK_DEMO_BUNDLE_TITLE,
        "version": "1",
        "content_digest": hashlib.sha256(QUICK_DEMO_SOURCE.encode()).hexdigest(),
    }


def _enrich_personas(environment: dict) -> None:
    group_indexes: dict[str, int] = {}
    for persona in environment["personas"]:
        group = persona["group"]
        profile = GROUP_PROFILES[group]
        index = group_indexes.get(group, 0)
        group_indexes[group] = index + 1
        persona.update(
            name=profile["names"][index],
            persona_name=profile["names"][index],
            role=profile["role"],
            profile=(
                f"{profile['role']} dengan perhatian utama pada "
                f"{profile['concern'].lower()}."
            ),
            concern=profile["concern"],
            concerns=[profile["concern"]],
            topics=profile["topics"],
        )


def _action_args(action: str, statement: str, previous: dict | None, concern: str) -> dict[str, Any]:
    if action == "QUOTE_POST":
        return {
            "quote_content": statement,
            "original_content": previous["statement"] if previous else concern,
            "original_author_name": previous["persona"] if previous else "Pemerintah daerah",
        }
    if action == "REPOST":
        return {
            "original_content": previous["statement"] if previous else statement,
            "original_author_name": previous["persona"] if previous else "Pelaksana MBG",
        }
    if action == "SEARCH_POSTS":
        return {"query": concern.lower()}
    if action in {"LIKE_POST", "LIKE_COMMENT", "UPVOTE_POST", "DOWNVOTE_POST"}:
        return {"post_content": previous["statement"] if previous else statement}
    return {"content": statement}


def _build_events(graph: dict, environment: dict) -> dict:
    personas_by_group = {
        group: next(persona for persona in environment["personas"] if persona["group"] == group)
        for group in GROUP_PROFILES
    }
    events: list[dict[str, Any]] = []
    groups = list(GROUP_PROFILES)
    for round_index, statements in enumerate(STATEMENTS):
        for group_index, group in enumerate(groups):
            persona = personas_by_group[group]
            statement = statements[group_index]
            action = ACTION_TYPES[round_index][group_index]
            previous = events[-1] if events else None
            stance = STANCES[round_index][group_index]
            concern = persona["concern"]
            events.append({
                "id": f"event-r{round_index + 1}-{group_index + 1}",
                "sequence": len(events) + 1,
                "round": round_index + 1,
                "time": f"2026-08-{6 + round_index:02d}T{9 + group_index:02d}:{group_index * 7:02d}:00+07:00",
                "channel": "twitter" if group_index % 2 == 0 else "reddit",
                "platform": "twitter" if group_index % 2 == 0 else "reddit",
                "persona_id": persona["id"],
                "persona": persona["name"],
                "persona_name": persona["name"],
                "group": group,
                "type": action,
                "event_type": action,
                "statement": statement,
                "content": statement,
                "stance": stance,
                "concerns": [concern, ROUND_THEMES[round_index]],
                "risk_narrative": (
                    f"{concern} dapat memperlebar kesenjangan partisipasi"
                    if stance == "Kritis"
                    else f"Mitigasi untuk {concern.lower()} mulai memengaruhi respons"
                ),
                "influence_source": (
                    "Pengalaman layanan dan percakapan lintas kelompok"
                    if round_index >= 2
                    else "Pengumuman kebijakan dan kondisi akses awal"
                ),
                "source_node_ids": persona["source_node_ids"],
                "citations": [],
                "graph_revision": graph["revision"],
                "config_version": environment["config"]["version"],
                "action_args": _action_args(action, statement, previous, concern),
                "success": True,
            })
    return {
        "id": f"run_{hashlib.sha256(QUICK_DEMO_BUNDLE_ID.encode()).hexdigest()[:12]}",
        "events": events,
        "event_count": len(events),
    }


def _build_runtime_graph(graph: dict, environment: dict) -> dict:
    policy_issues = [node for node in graph["nodes"] if node["type"] == "Issue"]
    nodes: list[dict[str, Any]] = []
    edges: list[dict[str, Any]] = []
    groups = list(GROUP_PROFILES)
    for index, (group, profile) in enumerate(GROUP_PROFILES.items()):
        group_id = f"runtime-group-{index + 1}"
        concern_id = f"runtime-concern-{index + 1}"
        nodes.extend([
            {
                "id": group_id,
                "label": group,
                "type": "PersonaGroup",
                "summary": f"Lima persona aktif dari kelompok {group}.",
            },
            {
                "id": concern_id,
                "label": profile["concern"],
                "type": "Concern",
                "summary": f"Perhatian yang memengaruhi respons {group.lower()} sepanjang simulasi.",
            },
        ])
        edges.append({
            "id": f"runtime-edge-raises-{index + 1}",
            "source": group_id,
            "target": concern_id,
            "type": "RAISES",
        })
        if index:
            edges.append({
                "id": f"runtime-edge-influence-{index + 1}",
                "source": f"runtime-group-{index}",
                "target": group_id,
                "type": "INFLUENCES",
            })
    for index, persona in enumerate(environment["personas"]):
        persona_id = f"runtime-persona-{index + 1}"
        group_index = groups.index(persona["group"]) + 1
        nodes.append({
            "id": persona_id,
            "label": persona["name"],
            "type": "Persona",
            "summary": persona["profile"],
        })
        edges.append({
            "id": f"runtime-edge-member-{index + 1}",
            "source": persona_id,
            "target": f"runtime-group-{group_index}",
            "type": "MEMBER_OF",
        })
    for index, issue in enumerate(policy_issues[:6]):
        issue_id = f"runtime-issue-{index + 1}"
        nodes.append({
            "id": issue_id,
            "label": issue["label"],
            "type": "PolicyIssue",
            "summary": issue["summary"],
        })
        edges.append({
            "id": f"runtime-edge-links-{index + 1}",
            "source": f"runtime-concern-{index + 1}",
            "target": issue_id,
            "type": "LINKS_TO",
        })
    for round_index, theme in enumerate(ROUND_THEMES, 1):
        phase_id = f"runtime-phase-{round_index}"
        nodes.append({
            "id": phase_id,
            "label": f"Ronde {round_index}: {theme}",
            "type": "SimulationPhase",
            "summary": f"Fase aktivitas dan perubahan sikap pada ronde {round_index}.",
        })
        for group_index in range(1, len(groups) + 1):
            edges.append({
                "id": f"runtime-edge-phase-{round_index}-{group_index}",
                "source": f"runtime-group-{group_index}",
                "target": phase_id,
                "type": "PARTICIPATES_IN",
            })
    return {
        "graph_id": "runtime-makan-bergizi-gratis",
        "graph_kind": "runtime",
        "source_revision": graph["revision"],
        "mapping_status": "completed",
        "nodes": nodes,
        "edges": edges,
        "node_count": len(nodes),
        "edge_count": len(edges),
    }


def _event_citation(event: dict) -> dict[str, Any]:
    return {
        "source_type": "event",
        "source_id": event["id"],
        "locator": {"round": event["round"], "channel": event["channel"]},
        "quote": event["statement"],
        "label": f"Ronde {event['round']} · {event['persona']}",
    }


def _build_report(simulation: dict) -> dict:
    events = simulation["events"]
    critical = [event for event in events if event["stance"] == "Kritis"]
    final_round = [event for event in events if event["round"] == 5]
    supporting = [
        events[6],
        events[13],
        events[20],
        events[24],
        events[28],
    ]
    citations = [_event_citation(event) for event in supporting]
    return {
        "id": "report-makan-bergizi-gratis",
        "version": 1,
        "title": "Laporan Simulasi Makan Bergizi Gratis (MBG)",
        "generated_by": "deterministic-local",
        "sections": [
            {
                "id": "ringkasan",
                "title": "Ringkasan Eksekutif",
                "paragraphs": [
                    f"Simulasi mencatat {len(events)} aktivitas dalam lima ronde. "
                    f"Sebanyak {len(critical)} aktivitas menunjukkan sikap kritis, terutama pada validitas data sasaran, "
                    "koordinasi pusat-daerah, kapasitas SPPG/rantai pasok, dan akuntabilitas pengadaan.",
                    "Klarifikasi desain belum cukup menurunkan keberatan karena prasyarat ekspansi, audit pengadaan, "
                    "dan bukti dampak independen belum menjadi syarat yang mengikat.",
                    "Arah respons publik tidak berubah karena satu pengumuman tunggal, melainkan karena rangkaian "
                    "klarifikasi yang dapat diverifikasi: dashboard evaluasi, audit pengadaan, peta kapasitas wilayah, "
                    "dan indikator dampak gizi.",
                    "Implikasi kebijakan utamanya adalah perlunya menahan ekspansi di wilayah belum siap dan menguji apakah "
                    "anggaran MBG lebih efektif dibanding intervensi gizi, sanitasi, dan pendidikan yang lebih terarah.",
                ],
                "citations": citations[:2],
            },
            {
                "id": "dinamika",
                "title": "Dinamika Respons",
                "paragraphs": [
                    "Percakapan bergerak dari dukungan umum terhadap tujuan MBG menuju keberatan terhadap data sasaran, "
                    "pembagian kewenangan, kapasitas SPPG, konflik pengadaan, dan lemahnya bukti dampak. Pada ronde ketiga, "
                    "peta kapasitas wilayah justru memperjelas bahwa beberapa lokasi belum layak dipaksa mengikuti ekspansi.",
                    f"Pada ronde akhir, {sum(event['stance'] == 'Mendukung' for event in final_round)} dari "
                    f"{len(final_round)} kelompok menunjukkan sikap mendukung.",
                    "BGN menjadi satu-satunya kelompok yang masih mencoba mempertahankan arah program, sementara daerah, sekolah, "
                    "SPPG, tenaga gizi, masyarakat sipil, dan media menuntut prasyarat yang lebih keras.",
                    "Media berperan sebagai penguat sinyal risiko: ketika indikator evaluasi belum mengikat, percakapan publik "
                    "menyoroti pemborosan, salah sasaran, konflik kepentingan, dan biaya peluang anggaran.",
                ],
                "citations": citations[1:4],
            },
            {
                "id": "sasaran",
                "title": "Ketepatan Sasaran dan Kapasitas Pelaksanaan",
                "paragraphs": [
                    "Mekanisme koreksi data penerima manfaat, peta kapasitas SPPG, dan indikator kesiapan sekolah belum layak "
                    "diperlakukan sebagai pelengkap; ketiganya harus menjadi syarat sebelum wilayah masuk ekspansi.",
                    "Koordinasi pusat-daerah menjadi titik lemah utama. Tanpa hak daerah untuk menunda atau mengoreksi pelaksanaan, "
                    "risiko lapangan hanya dipindahkan dari pusat ke sekolah dan pemerintah daerah.",
                    "Segmentasi evaluasi juga masih lemah. Sekolah menanggung administrasi, SPPG menanggung risiko pembayaran, "
                    "sedangkan tenaga gizi belum mendapat bukti bahwa dampak gizi lebih kuat daripada intervensi alternatif.",
                ],
                "citations": citations[0:3],
            },
            {
                "id": "akuntabilitas",
                "title": "Akuntabilitas Pembiayaan dan Evaluasi Publik",
                "paragraphs": [
                    "Penjelasan standar pengadaan, audit pemasok, dan penggunaan anggaran belum cukup. Tanpa transparansi kontrak "
                    "dan penerima manfaat akhir, risiko konflik kepentingan tetap tinggi.",
                    "Komunikasi kebijakan sebaiknya memisahkan output penyaluran, kualitas layanan, dampak gizi, dan akuntabilitas "
                    "anggaran. Data pribadi siswa tetap perlu dilindungi agar transparansi tidak membuka informasi sensitif.",
                    "Kepercayaan hanya mungkin dipulihkan jika BGN menerbitkan ringkasan pengawasan yang membuka cakupan sasaran, "
                    "kesiapan wilayah, realisasi anggaran, penerima kontrak, keluhan, hasil audit, dan wilayah yang ditunda.",
                ],
                "citations": citations[2:5],
            },
            {
                "id": "rekomendasi",
                "title": "Prioritas Tindak Lanjut",
                "paragraphs": [
                    "Tahan ekspansi nasional di wilayah yang belum memenuhi kriteria kesiapan, validitas data penerima manfaat, "
                    "kapasitas SPPG, audit pengadaan, dan dukungan administrasi sekolah.",
                    "Terbitkan laporan berkala mengenai cakupan sasaran, realisasi anggaran, proses pengadaan, keluhan, "
                    "kualitas layanan, dan indikator dampak gizi.",
                    "Prioritaskan tiga metrik keputusan untuk evaluasi bulan berikutnya: exclusion error penerima manfaat, "
                    "persentase wilayah dengan kapasitas SPPG memadai, dan bukti dampak gizi independen. Jika salah satu "
                    "tidak memenuhi ambang minimum, ekspansi harus ditunda.",
                    "Bentuk forum review berkala yang menggabungkan BGN, pemerintah daerah, sekolah, SPPG/pemasok, tenaga kesehatan, "
                    "dan pengawas publik. Forum ini bertugas meninjau tradeoff desain, memperbarui pedoman, dan menentukan prioritas koreksi.",
                ],
                "citations": citations[3:5],
            },
        ],
        "risks": [
            {
                "id": "risk-targeting",
                "title": "Program tidak tepat sasaran",
                "level": "Tinggi",
                "trend": "Meningkat",
                "evidence": "Risiko exclusion error, data sasaran yang sulit dikoreksi, dan variasi kondisi wilayah muncul lintas ronde.",
                "citations": citations[:2],
            },
            {
                "id": "risk-governance",
                "title": "Ekspansi mendahului kapasitas wilayah",
                "level": "Tinggi",
                "trend": "Stabil",
                "evidence": "Mandat pusat, beban sekolah, dan kapasitas SPPG tetap tidak seimbang meskipun ada klarifikasi.",
                "citations": citations[2:4],
            },
            {
                "id": "risk-accountability",
                "title": "Akuntabilitas pembiayaan dan pengadaan lemah",
                "level": "Tinggi",
                "trend": "Meningkat",
                "evidence": "Transparansi anggaran, konflik kepentingan, audit pemasok, dan biaya peluang tetap menjadi keberatan utama.",
                "citations": citations[1:5],
            },
        ],
        "citations": citations,
    }


def build_quick_demo(provider: Any) -> tuple[dict, dict, dict, dict, dict, dict]:
    """Build stable, validated artifacts from the curated source."""
    project = {
        "id": QUICK_DEMO_BUNDLE_ID,
        "name": QUICK_DEMO_BUNDLE_TITLE,
        "project_name": QUICK_DEMO_BUNDLE_TITLE,
        "institution": "Badan Gizi Nasional",
        "objective": (
            "Mengkritisi desain tata kelola nasional MBG terhadap risiko salah sasaran, "
            "ekspansi terlalu cepat, akuntabilitas pengadaan, dan biaya peluang anggaran."
        ),
    }
    chunk = {
        "id": "quick-demo-source",
        "document_id": "quick-demo-bundle",
        "ordinal": 0,
        "text": QUICK_DEMO_SOURCE,
        "char_start": 0,
        "char_end": len(QUICK_DEMO_SOURCE),
    }
    ontology = provider.ontology(project, [chunk])
    graph = provider.graph(project, ontology, [chunk])

    stakeholder_details = [
        (group, profile["role"])
        for group, profile in GROUP_PROFILES.items()
    ]
    for node, (label, summary) in zip(
        (item for item in graph["nodes"] if item["type"] == "Stakeholder"),
        stakeholder_details,
        strict=True,
    ):
        node.update(label=label, summary=summary)

    issue_details = [
        ("Risiko salah sasaran MBG", "Exclusion error, inclusion error, dan lemahnya mekanisme koreksi penerima manfaat."),
        ("Beban pusat-daerah-sekolah", "Mandat pelaksanaan yang tidak sebanding dengan kapasitas, anggaran, dan tenaga administrasi."),
        ("Ekspansi mendahului kapasitas", "Kesiapan SPPG, pemasok lokal, logistik, pembayaran, dan pengawasan wilayah."),
        ("Akuntabilitas pengadaan", "Transparansi anggaran, konsentrasi kontrak, konflik kepentingan, dan audit pemasok."),
        ("Biaya peluang anggaran", "Tradeoff MBG terhadap intervensi gizi, sanitasi, kesehatan, dan pendidikan lain."),
        ("Bukti dampak gizi lemah", "Kesenjangan antara jumlah porsi tersalurkan dan hasil gizi yang dapat diverifikasi."),
    ]
    for node, (label, summary) in zip(
        (item for item in graph["nodes"] if item["type"] == "Issue"),
        issue_details,
        strict=True,
    ):
        node.update(label=label, summary=summary)

    # The source is packaged with the application and has no user document ID.
    ontology["citations"] = []
    for item in graph["nodes"] + graph["edges"]:
        item["citations"] = []

    environment = provider.environment(QUICK_DEMO_BUNDLE_ID, graph, {
        "rounds": 5,
        "socialization": "Sedang",
        "response_mode": "Responsif",
        "fixture": QUICK_DEMO_BUNDLE_ID,
    })
    environment["config"].update(
        channels=["twitter", "reddit"],
        platforms=["twitter", "reddit"],
        total_simulation_hours=20,
        minutes_per_round=240,
        events_per_round=6,
    )
    _enrich_personas(environment)
    simulation = _build_events(graph, environment)
    runtime_graph = _build_runtime_graph(graph, environment)
    report = ReportOutput.model_validate(_build_report(simulation)).model_dump()
    return ontology, graph, environment, simulation, runtime_graph, report
