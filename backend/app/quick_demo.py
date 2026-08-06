from __future__ import annotations

import hashlib
from typing import Any

from .provider_contracts import ReportOutput


QUICK_DEMO_BUNDLE_ID = "registrasi-digital-umkm-v1"
QUICK_DEMO_BUNDLE_TITLE = "Registrasi Digital UMKM"
QUICK_DEMO_SOURCE = """
Pemerintah daerah akan menerapkan registrasi digital bagi pelaku UMKM untuk
memperbarui data usaha, mempermudah akses bantuan, dan menghubungkan perizinan
dengan layanan pembiayaan. Pelaksanaan dimulai dengan sosialisasi selama tiga
bulan, dilanjutkan masa transisi enam bulan sebelum registrasi menjadi syarat
utama untuk mengakses program bantuan baru.

Pelaku usaha mikro menghadapi hambatan literasi digital, kepemilikan perangkat,
konektivitas, biaya adaptasi, dan kekhawatiran mengenai penggunaan data pribadi.
Layanan luring di kantor kecamatan dan pendampingan koperasi tetap tersedia
selama masa transisi. Pemerintah daerah menyiapkan meja bantuan, nomor pengaduan,
pelatihan gratis, serta prosedur koreksi data tanpa biaya.

Koperasi, pendamping UMKM, penyedia teknologi, akademisi, organisasi masyarakat
sipil, dan media lokal dilibatkan untuk memantau akses, keamanan data, waktu
layanan, serta dampak terhadap usaha perempuan, pedagang pasar, usaha rumahan,
dan pelaku usaha di wilayah dengan konektivitas rendah. Evaluasi bulanan akan
menentukan kebutuhan perpanjangan masa transisi dan pengecualian sementara.
""".strip()

GROUP_PROFILES = {
    "Pemerintah daerah": {
        "names": ["Ratna Prameswari", "Dedi Kurniawan", "Nina Ardianti", "Agus Santoso", "Farah Maulida"],
        "role": "Pengelola layanan UMKM daerah",
        "concern": "Kesiapan layanan dan konsistensi informasi",
        "topics": ["masa transisi", "meja bantuan", "koreksi data"],
    },
    "Pelaku usaha": {
        "names": ["Sari Wulandari", "Bambang Riyadi", "Nur Aini", "Hendra Gunawan", "Lilis Setiawati"],
        "role": "Pemilik usaha mikro",
        "concern": "Biaya adaptasi dan akses perangkat",
        "topics": ["biaya adaptasi", "akses perangkat", "bantuan usaha"],
    },
    "Warga terdampak": {
        "names": ["Yuni Hartati", "Rizal Akbar", "Murniati", "Taufik Hidayat", "Dewi Lestari"],
        "role": "Pelanggan dan anggota keluarga pelaku usaha",
        "concern": "Akses layanan luring dan waktu tunggu",
        "topics": ["layanan luring", "konektivitas", "waktu layanan"],
    },
    "Akademisi": {
        "names": ["Dr. Maya Kusuma", "Rafi Pradana", "Intan Permata", "Bagus Wicaksono", "Rina Oktaviani"],
        "role": "Peneliti kebijakan ekonomi digital",
        "concern": "Indikator evaluasi dan kesenjangan akses",
        "topics": ["indikator evaluasi", "inklusi digital", "kualitas data"],
    },
    "Masyarakat sipil": {
        "names": ["Alya Ramadhani", "Fikri Anwar", "Siska Melati", "Joko Saputra", "Nadia Putri"],
        "role": "Pendamping hak digital dan UMKM",
        "concern": "Perlindungan data dan mekanisme pengaduan",
        "topics": ["perlindungan data", "persetujuan", "pengaduan"],
    },
    "Media lokal": {
        "names": ["Andi Prasetyo", "Mega Puspita", "Reza Firmansyah", "Tari Anggraini", "Ilham Nugraha"],
        "role": "Jurnalis ekonomi daerah",
        "concern": "Kejelasan informasi dan verifikasi klaim",
        "topics": ["informasi publik", "verifikasi", "dampak lapangan"],
    },
}

ROUND_THEMES = [
    "Pengumuman awal dan pemahaman persyaratan",
    "Hambatan akses dan kekhawatiran data",
    "Penyebaran pengalaman lapangan",
    "Klarifikasi layanan dan langkah mitigasi",
    "Evaluasi respons dan perubahan sikap",
]

STATEMENTS = [
    [
        "Registrasi dibuka bertahap; meja bantuan kecamatan dan kanal pengaduan mulai beroperasi pekan ini.",
        "Saya mendukung pendataan yang lebih rapi, tetapi pedagang kecil perlu tahu biaya dan dokumen apa saja yang diminta.",
        "Warga di pinggiran kota masih bertanya apakah pendaftaran bisa diselesaikan tanpa ponsel pintar.",
        "Keberhasilan tahap awal perlu diukur dari tingkat penyelesaian, waktu layanan, dan kesenjangan antarwilayah.",
        "Informasi persetujuan penggunaan data harus tampil sebelum pelaku usaha mengirim formulir.",
        "Banyak pertanyaan masuk tentang tenggat, sanksi, dan keberlanjutan layanan luring selama transisi.",
    ],
    [
        "Dinas menambah jadwal layanan bergerak untuk pasar tradisional dan wilayah dengan konektivitas rendah.",
        "Unggah dokumen beberapa kali gagal dan biaya fotokopi serta perjalanan mulai terasa bagi usaha harian.",
        "Antrean di kecamatan lebih panjang pada pagi hari karena petugas membantu koreksi nomor identitas usaha.",
        "Data awal menunjukkan hambatan terbesar bukan penolakan, melainkan perangkat, jaringan, dan bantuan langsung.",
        "Pelaku usaha perlu memperoleh penjelasan siapa yang dapat mengakses data dan berapa lama data disimpan.",
        "Laporan gangguan unggah dan antrean mulai ramai, tetapi lokasi meja bantuan belum dipublikasikan secara konsisten.",
    ],
    [
        "Panduan satu halaman dan daftar lokasi pendamping kini dibagikan melalui kelurahan, koperasi, dan pasar.",
        "Pendamping koperasi membantu saya menyelesaikan registrasi, tetapi pemilik usaha rumahan lain belum mendapat informasi.",
        "Kabar bahwa bantuan lama langsung dihentikan ternyata tidak benar, namun klarifikasi resminya terlambat menyebar.",
        "Perbedaan informasi antarpetugas berisiko menurunkan kepercayaan meskipun kebijakan transisinya cukup inklusif.",
        "Kami menerima aduan tentang formulir persetujuan yang terlalu umum dan meminta penjelasan tujuan setiap data.",
        "Cerita keberhasilan pendampingan mulai muncul bersamaan dengan keluhan tentang kualitas jaringan dan respons petugas.",
    ],
    [
        "Dinas menegaskan tidak ada sanksi selama masa transisi dan menerbitkan standar waktu penyelesaian tiga hari kerja.",
        "Kepastian tanpa sanksi membantu, tetapi jadwal pelatihan perlu tersedia setelah jam berdagang.",
        "Layanan bergerak mengurangi perjalanan, meski warga masih membutuhkan bukti tertulis setelah koreksi data.",
        "Standar layanan baru dapat diuji dengan mempublikasikan waktu tunggu, kegagalan unggah, dan penyelesaian aduan.",
        "Perubahan formulir persetujuan dan opsi menghapus lampiran yang salah merupakan langkah perbaikan yang penting.",
        "Klarifikasi mulai menekan rumor, tetapi pelaksanaan di setiap kecamatan perlu dibandingkan secara terbuka.",
    ],
    [
        "Evaluasi bulan pertama menunjukkan peningkatan penyelesaian setelah layanan bergerak dan panduan ringkas diterapkan.",
        "Saya lebih siap mendaftar setelah ada pendampingan dan kepastian masa transisi, meski dukungan perangkat tetap dibutuhkan.",
        "Akses luring membuat proses lebih adil; berikutnya warga membutuhkan jadwal tetap dan nomor tiket pengaduan.",
        "Sikap membaik ketika mitigasi dapat diverifikasi, tetapi indikator kelompok rentan harus terus dipisahkan.",
        "Risiko privasi menurun setelah penjelasan diperbaiki, namun audit akses data tetap perlu diumumkan berkala.",
        "Percakapan bergeser dari penolakan umum menuju pengawasan mutu layanan, biaya, dan perlindungan data.",
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
    ["Mendukung", "Netral", "Kritis", "Netral", "Kritis", "Netral"],
    ["Mendukung", "Kritis", "Kritis", "Netral", "Kritis", "Kritis"],
    ["Mendukung", "Netral", "Netral", "Kritis", "Kritis", "Netral"],
    ["Mendukung", "Netral", "Mendukung", "Mendukung", "Netral", "Netral"],
    ["Mendukung", "Mendukung", "Mendukung", "Mendukung", "Netral", "Mendukung"],
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
            "original_author_name": previous["persona"] if previous else "Pelaku UMKM",
        }
    if action == "REPOST":
        return {
            "original_content": previous["statement"] if previous else statement,
            "original_author_name": previous["persona"] if previous else "Pendamping UMKM",
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
        "graph_id": "runtime-registrasi-digital-umkm",
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
        "id": "report-registrasi-digital-umkm",
        "version": 1,
        "title": "Laporan Simulasi Registrasi Digital UMKM",
        "generated_by": "deterministic-local",
        "sections": [
            {
                "id": "ringkasan",
                "title": "Ringkasan Eksekutif",
                "paragraphs": [
                    f"Simulasi mencatat {len(events)} aktivitas dalam lima ronde. "
                    f"Sebanyak {len(critical)} aktivitas menunjukkan sikap kritis, terutama pada akses perangkat, "
                    "biaya adaptasi, perlindungan data, dan konsistensi layanan.",
                    "Respons membaik setelah kepastian masa transisi, layanan bergerak, standar waktu layanan, "
                    "dan perbaikan formulir persetujuan diumumkan.",
                    "Arah respons publik tidak berubah karena satu pengumuman tunggal, melainkan karena rangkaian "
                    "klarifikasi yang dapat diverifikasi: lokasi pendamping, tidak adanya sanksi selama transisi, "
                    "bukti koreksi data, dan komitmen membuka kanal pengaduan.",
                    "Implikasi kebijakan utamanya adalah kebutuhan menjaga dua lintasan layanan secara bersamaan: "
                    "jalur digital untuk mempercepat pembaruan data dan jalur pendampingan tatap muka untuk menjaga "
                    "akses pelaku usaha yang belum siap secara perangkat, literasi, atau konektivitas.",
                ],
                "citations": citations[:2],
            },
            {
                "id": "dinamika",
                "title": "Dinamika Respons",
                "paragraphs": [
                    "Percakapan bergerak dari pertanyaan tentang persyaratan menuju pengalaman kegagalan unggah, "
                    "antrean, dan akses luring. Pada ronde ketiga, pengalaman pendampingan mulai mengurangi rumor, "
                    "namun perbedaan informasi antarpetugas masih menekan kepercayaan.",
                    f"Pada ronde akhir, {sum(event['stance'] == 'Mendukung' for event in final_round)} dari "
                    f"{len(final_round)} kelompok menunjukkan sikap mendukung.",
                    "Kelompok pemerintah daerah dan pelaku usaha merespons positif ketika standar layanan dibuat "
                    "lebih konkret, sementara masyarakat sipil dan akademisi tetap menjaga tekanan pada bukti, "
                    "indikator kelompok rentan, serta tata kelola data.",
                    "Media lokal berperan sebagai penguat sinyal risiko: ketika lokasi meja bantuan belum konsisten, "
                    "percakapan publik menyoroti antrean dan rumor sanksi; ketika klarifikasi diterbitkan, fokus bergeser "
                    "ke mutu layanan, biaya adaptasi, dan konsistensi pelaksanaan antar kecamatan.",
                ],
                "citations": citations[1:4],
            },
            {
                "id": "akses",
                "title": "Akses dan Inklusi",
                "paragraphs": [
                    "Layanan bergerak dan meja bantuan kecamatan mengurangi hambatan perjalanan dan perangkat. "
                    "Jadwal setelah jam berdagang, bukti koreksi tertulis, serta nomor tiket pengaduan tetap "
                    "dibutuhkan agar manfaatnya merata.",
                    "Kanal luring perlu dipertahankan sebagai bagian inti desain layanan, bukan sekadar kompensasi "
                    "sementara. Tanpa jadwal tetap, antrean terukur, dan dukungan koperasi, kelompok usaha rumahan "
                    "serta wilayah berkoneksi rendah masih berisiko tertinggal.",
                    "Segmentasi dukungan juga perlu lebih rinci. Pedagang pasar membutuhkan jam layanan yang tidak "
                    "mengganggu waktu berdagang, usaha rumahan membutuhkan informasi melalui kanal kelurahan dan koperasi, "
                    "sedangkan wilayah pinggiran membutuhkan layanan bergerak dengan jadwal yang diumumkan lebih awal.",
                ],
                "citations": citations[0:3],
            },
            {
                "id": "data",
                "title": "Perlindungan Data dan Kepercayaan",
                "paragraphs": [
                    "Penjelasan tujuan penggunaan data dan opsi memperbaiki lampiran menurunkan kekhawatiran. "
                    "Audit akses data dan publikasi penyelesaian aduan diperlukan untuk mempertahankan kepercayaan.",
                    "Materi persetujuan sebaiknya ditulis dalam bahasa ringkas, memisahkan data wajib dan opsional, "
                    "serta menjelaskan siapa yang dapat mengakses data usaha. Mekanisme hapus atau koreksi lampiran "
                    "perlu ditampilkan sebelum pengguna mengirim formulir.",
                    "Kepercayaan akan lebih mudah dipertahankan jika pemerintah daerah menerbitkan ringkasan tata kelola "
                    "data: tujuan pengumpulan, masa simpan, hak koreksi, kontak pengaduan, dan mekanisme audit internal. "
                    "Ringkasan ini harus tersedia di laman digital dan meja bantuan luring.",
                ],
                "citations": citations[2:5],
            },
            {
                "id": "rekomendasi",
                "title": "Prioritas Tindak Lanjut",
                "paragraphs": [
                    "Pertahankan layanan luring selama masa transisi, publikasikan standar layanan per kecamatan, "
                    "sediakan pelatihan di luar jam usaha, dan pisahkan indikator akses untuk kelompok rentan.",
                    "Terbitkan laporan bulanan mengenai waktu tunggu, kegagalan unggah, koreksi data, dan penyelesaian "
                    "pengaduan sebelum registrasi menjadi syarat bantuan baru.",
                    "Prioritaskan tiga metrik keputusan untuk evaluasi bulan berikutnya: persentase registrasi selesai "
                    "tanpa kunjungan ulang, waktu median koreksi data, dan proporsi aduan yang menerima nomor tiket. "
                    "Jika salah satu memburuk, masa transisi perlu diperpanjang secara terbatas di wilayah terdampak.",
                    "Bentuk tim respons mingguan yang menggabungkan dinas, kecamatan, koperasi, dan perwakilan pendamping. "
                    "Tim ini bertugas meninjau keluhan berulang, memperbarui FAQ publik, dan memutuskan apakah materi "
                    "sosialisasi perlu disesuaikan untuk kelompok usaha atau wilayah tertentu.",
                ],
                "citations": citations[3:5],
            },
        ],
        "risks": [
            {
                "id": "risk-access",
                "title": "Kesenjangan akses digital",
                "level": "Tinggi",
                "trend": "Menurun",
                "evidence": "Hambatan perangkat, jaringan, perjalanan, dan waktu layanan muncul lintas ronde.",
                "citations": citations[:2],
            },
            {
                "id": "risk-data",
                "title": "Ketidakjelasan penggunaan data",
                "level": "Sedang",
                "trend": "Menurun",
                "evidence": "Kekhawatiran berkurang setelah formulir persetujuan dan koreksi data diperjelas.",
                "citations": citations[2:4],
            },
            {
                "id": "risk-service",
                "title": "Ketidakkonsistenan layanan kecamatan",
                "level": "Sedang",
                "trend": "Stabil",
                "evidence": "Perbedaan informasi dan mutu pelaksanaan masih membutuhkan pemantauan terbuka.",
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
        "institution": "Dinas Koperasi dan UMKM",
        "objective": (
            "Menilai respons pelaku UMKM terhadap registrasi digital dan "
            "mengidentifikasi narasi risiko yang perlu diklarifikasi."
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

    issue_details = [
        ("Registrasi digital", "Persyaratan, tahapan, dan tenggat registrasi usaha."),
        ("Akses perangkat", "Ketersediaan perangkat untuk pelaku usaha mikro."),
        ("Konektivitas", "Kualitas jaringan di pasar dan wilayah pinggiran."),
        ("Perlindungan data", "Persetujuan, akses, penyimpanan, dan koreksi data."),
        ("Biaya adaptasi", "Biaya waktu, perjalanan, dokumen, dan perangkat."),
        ("Layanan luring", "Ketersediaan pendampingan dan alternatif tatap muka."),
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
