"""
TEKNOFEST 2026 Uluslararası İHA - Saha Operasyonları, 4 Uçuş Hakkı & Kronometre Yöneticisi
==========================================================================================
Şartname Referansları:
  - Madde 8.3.1: Toplam en fazla 4 uçuş hakkı; her görevde en yüksek skor baz alınır.
  - Madde 10.1 & 10.2: Görev 1'i başarıyla tamamlayamayan takım Görev 2'ye geçemez.
  - Madde 8.3.5:
      * Kurulum süresi <= 8 dk (480s)
      * Uçuşa hazırlık süresi <= 8 dk (480s)
      * Görev 1 uçuş süresi <= 5 dk (300s)
      * Görev 2 uçuş süresi <= 10 dk (600s)
      * Güç kesme/verme harici her müdahale: müdahale süresi + 10s ceza.
  - Saha Ekibi Kotası: En fazla 4 üye (Danışman sahaya giremez), baret + SHGM karekod zorunlu.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


class AttemptStatus(Enum):
    SUCCESS = "SUCCESS"
    FAILED_TIME_LIMIT = "FAILED_TIME_LIMIT"
    FAILED_SETUP_LIMIT = "FAILED_SETUP_LIMIT"
    ABORTED_SAFETY = "ABORTED_SAFETY"


@dataclass
class FieldCrewRoster:
    """Uçuş sahasına çıkacak takım üyeleri ve zorunlu güvenlik doğrulaması."""
    member_names: List[str]
    advisor_on_field: bool = False
    all_helmets_worn: bool = True
    shgm_qr_verified: bool = True
    power_cut_2s_verified: bool = True


@dataclass
class FlightAttemptRecord:
    """Tek bir resmi uçuş denemesinin kaydı."""
    attempt_number: int
    task_number: int                        # 1 veya 2
    setup_duration_s: float
    prep_duration_s: float
    flight_duration_s: float
    extra_interventions_s: List[float]
    effective_setup_s: float
    raw_score: float
    valid_score: float
    status: AttemptStatus
    notes: str = ""


@dataclass
class CompetitionStandingSummary:
    """4 uçuş hakkı boyunca takımın anlık yarışma durumu ve taktik önerisi."""
    attempts_used: int
    attempts_remaining: int
    task1_qualified: bool
    best_task1_score: float
    best_task2_score: float
    video_score: float
    combined_total_score: float
    crew_compliant: bool
    crew_violations: List[str]
    tactical_recommendation: str


class CompetitionAttemptManager:
    """
    4 Uçuş Hakkı, Görev 1 Ön Koşulu, Kronometre Cezaları ve Saha Ekibi Uyumluluk Yöneticisi.
    """

    MAX_ATTEMPTS = 4
    SETUP_LIMIT_S = 480.0
    PREP_LIMIT_S = 480.0
    TASK_1_FLIGHT_LIMIT_S = 300.0
    TASK_2_FLIGHT_LIMIT_S = 600.0
    EXTRA_INTERVENTION_PENALTY_S = 10.0

    def __init__(self, team_name: str = "UAV-ARCHITECT-GLOBAL", video_score: float = 9.5):
        self.team_name = team_name
        self.video_score = max(0.0, min(10.0, float(video_score)))
        self.attempts: List[FlightAttemptRecord] = []
        self.crew_roster: Optional[FieldCrewRoster] = None

    def set_crew_roster(self, roster: FieldCrewRoster) -> List[str]:
        """Saha ekibini Şartname §8.3.1 & §9.4 kurallarına göre doğrular."""
        self.crew_roster = roster
        return self.validate_crew(roster)

    @staticmethod
    def validate_crew(roster: FieldCrewRoster) -> List[str]:
        violations: List[str] = []
        if len(roster.member_names) == 0:
            violations.append("Saha ekibi boş olamaz.")
        if len(roster.member_names) > 4:
            violations.append(f"Saha takım kotası aşıldı: {len(roster.member_names)} > 4 üye (§8.3.1).")
        if roster.advisor_on_field:
            violations.append("Takım danışmanlarının uçuş sahasına girmesi KESİNLİKLE YASAKTIR (§8.3.1).")
        if not roster.all_helmets_worn:
            violations.append("Tüm saha üyelerinin TÜBİTAK baretini takması zorunludur (§9.4).")
        if not roster.shgm_qr_verified:
            violations.append("SHGM pilot/İHA kaydı ve karekod doğrulaması eksik.")
        if not roster.power_cut_2s_verified:
            violations.append("2 saniye acil güç kesme anahtarı hakem doğrulaması eksik (§9.3.4).")
        return violations

    @property
    def task1_qualified(self) -> bool:
        return any(a.task_number == 1 and a.status == AttemptStatus.SUCCESS for a in self.attempts)

    def record_attempt(
        self,
        task_number: int,
        setup_duration_s: float,
        prep_duration_s: float,
        flight_duration_s: float,
        raw_score: float,
        extra_interventions_s: Optional[List[float]] = None,
        aborted_safety: bool = False,
        notes: str = "",
    ) -> FlightAttemptRecord:
        """Yeni bir resmi uçuş hakkını kurallara göre kaydeder ve puanlar."""
        if len(self.attempts) >= self.MAX_ATTEMPTS:
            raise ValueError("Maksimum 4 uçuş hakkının tamamı kullanıldı (§8.3.1).")
        if task_number not in (1, 2):
            raise ValueError("Görev numarası 1 veya 2 olmalıdır.")
        if task_number == 2 and not self.task1_qualified:
            raise PermissionError("Görev 1 başarıyla tamamlanmadan Görev 2 uçuşu başlatılamaz (§10.1/§10.2).")

        interventions = list(extra_interventions_s or [])
        eff_setup = setup_duration_s + sum(max(0.0, dt) + self.EXTRA_INTERVENTION_PENALTY_S for dt in interventions)
        flight_limit = self.TASK_1_FLIGHT_LIMIT_S if task_number == 1 else self.TASK_2_FLIGHT_LIMIT_S

        if aborted_safety:
            status = AttemptStatus.ABORTED_SAFETY
            valid_score = 0.0
        elif eff_setup > self.SETUP_LIMIT_S or prep_duration_s > self.PREP_LIMIT_S:
            status = AttemptStatus.FAILED_SETUP_LIMIT
            valid_score = 0.0
        elif flight_duration_s > flight_limit:
            status = AttemptStatus.FAILED_TIME_LIMIT
            valid_score = 0.0
        else:
            status = AttemptStatus.SUCCESS
            valid_score = max(0.0, float(raw_score))

        rec = FlightAttemptRecord(
            attempt_number=len(self.attempts) + 1,
            task_number=task_number,
            setup_duration_s=round(setup_duration_s, 2),
            prep_duration_s=round(prep_duration_s, 2),
            flight_duration_s=round(flight_duration_s, 2),
            extra_interventions_s=interventions,
            effective_setup_s=round(eff_setup, 2),
            raw_score=round(raw_score, 2),
            valid_score=round(valid_score, 2),
            status=status,
            notes=notes,
        )
        self.attempts.append(rec)
        return rec

    def get_summary(self) -> CompetitionStandingSummary:
        """Takımın 4 hak içerisindeki en iyi skorlarını ve bir sonraki sorti önerisini döndürür."""
        best_g1 = max((a.valid_score for a in self.attempts if a.task_number == 1), default=0.0)
        best_g2 = max((a.valid_score for a in self.attempts if a.task_number == 2), default=0.0)
        used = len(self.attempts)
        rem = self.MAX_ATTEMPTS - used

        crew_violations = self.validate_crew(self.crew_roster) if self.crew_roster else []
        crew_ok = len(crew_violations) == 0

        if rem == 0:
            rec = "Tüm 4 uçuş hakkı tamamlandı. Hakem adli raporunu ve kara kutu kanıtlarını teslim edin."
        elif not self.task1_qualified:
            rec = f"ÖNCELİK: Görev 1 (2 tur ∞) tamamlanmalı (Kalan hak: {rem}). Güvenli otonom profille G1 kilidini açın."
        elif best_g2 == 0.0:
            rec = f"Görev 1 onaylı ({best_g1:.1f} puan). Kalan {rem} hakta Görev 2'ye güvenli 1. yük profiliyle çıkın."
        else:
            rec = (
                f"G1 ({best_g1:.1f}) ve G2 ({best_g2:.1f}) güvende! Kalan {rem} hakta 2. yük ağırlığı denemesi "
                f"(agresif W_yuk) ve Görev 3 AY/BY bonusuyla skoru maksimize edin."
            )

        return CompetitionStandingSummary(
            attempts_used=used,
            attempts_remaining=rem,
            task1_qualified=self.task1_qualified,
            best_task1_score=round(best_g1, 2),
            best_task2_score=round(best_g2, 2),
            video_score=round(self.video_score, 2),
            combined_total_score=round(self.video_score + best_g1 + best_g2, 2),
            crew_compliant=crew_ok,
            crew_violations=crew_violations,
            tactical_recommendation=rec,
        )
