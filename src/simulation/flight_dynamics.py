"""
6-DOF (Degrees-of-Freedom) Non-Linear Flight Dynamics & Aerodynamic Physics Engine
==================================================================================
TEKNOFEST 2026 Uluslararası İHA ve Savaşan İHA için Yüksek Hassasiyetli Uçuş Fiziği.

Bu modül:
- 12 Durumlu Newton-Euler Tam 6-DOF Hareket Denklemleri (Translational + Rotational)
- Aerodinamik Kuvvet ve Momentler (Taşıma, Sürükleme, Yan Kuvvet, Yatış, Yunuslama, Sapma)
- Hücum Açısı (Alpha), Kayma Açısı (Beta) ve Dinamik Basınç (q_bar)
- Kontrol Yüzeyleri: İrtifa Dümeni (Elevator), Kanatçık (Aileron), İstikamet (Rudder), Gaz (Throttle)
- 4. Dereceden Runge-Kutta (RK4) Sayısal Entegratörü
- Rüzgar ve Türbülans Vektörü Entegrasyonu
sağlar.
"""

import math
from typing import Tuple, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class AircraftAeroParams:
    """İHA aerodinamik ve atalet parametreleri (2.6 kg Sabit Kanat / VTOL İHA)."""
    mass_kg: float = 2.60          # Toplam kalkış ağırlığı
    wing_area_m2: float = 0.45     # Kanat alanı (S)
    wing_span_m: float = 1.40      # Kanat açıklığı (b)
    mean_chord_m: float = 0.32     # Ortalama aerodinamik veter (c_bar)
    
    # Atalet Tensörü (kg * m^2)
    ixx: float = 0.085
    iyy: float = 0.125
    izz: float = 0.190
    
    # Taşıma (Lift) Katsayıları
    cl_0: float = 0.28             # Sıfır hücum açısı taşıma katsayısı
    cl_alpha: float = 4.8          # dCL / dAlpha (rad^-1)
    cl_delta_e: float = 0.40       # Elevatör taşıma etkisi
    
    # Sürükleme (Drag) Katsayıları
    cd_0: float = 0.032            # Parazit sürükleme katsayısı
    induced_drag_k: float = 0.045  # İndüklenmiş sürükleme faktörü (k * CL^2)
    
    # Yan Kuvvet (Sideforce)
    cy_beta: float = -0.75         # dCY / dBeta
    cy_delta_r: float = 0.18       # Rudder yan kuvvet etkisi
    
    # Yunuslama Momenti (Pitching Moment)
    cm_0: float = 0.02
    cm_alpha: float = -0.55        # Boyuna statik kararlılık (negatif olmalı)
    cm_q: float = -8.5             # Yunuslama sönümleme türevi
    cm_delta_e: float = -0.95      # Elevatör otoritesi
    
    # Yatış Momenti (Rolling Moment)
    cl_beta: float = -0.10         # Dihedral etkisi
    cl_p: float = -0.45            # Roll sönümleme
    cl_delta_a: float = 0.22       # Aileron otoritesi
    
    # Sapma Momenti (Yawing Moment)
    cn_beta: float = 0.14          # Yön kararlılığı (pozitif olmalı)
    cn_r: float = -0.18            # Yaw sönümleme
    cn_delta_r: float = -0.09      # Rudder otoritesi

    # Maksimum İtki (Newton)
    max_thrust_n: float = 24.0     # ~2.4 kgf itki (T/W ~ 0.92)


@dataclass
class AircraftState6DOF:
    """12 Durumlu 6-DOF Uçuş Durumu."""
    # NED Konum (m)
    pos_n: float = 0.0
    pos_e: float = 0.0
    pos_d: float = -30.0  # -30m NED = 30m AGL irtifa
    
    # Gövde Hızları (m/s: u-ileri, v-sağ, w-aşağı)
    u: float = 18.0
    v: float = 0.0
    w: float = 0.0
    
    # Euler Açıları (rad: phi-roll, theta-pitch, psi-yaw)
    phi: float = 0.0
    theta: float = 0.0
    psi: float = 0.0
    
    # Açısal Hızlar (rad/s: p-roll rate, q-pitch rate, r-yaw rate)
    p: float = 0.0
    q: float = 0.0
    r: float = 0.0


@dataclass
class ControlInputs:
    """İHA Kontrol Yüzeyi Komutları."""
    throttle: float = 0.55  # [0.0, 1.0] Motor gazı
    elevator_rad: float = 0.0  # [-0.35, +0.35] rad (~20 deg)
    aileron_rad: float = 0.0   # [-0.35, +0.35] rad
    rudder_rad: float = 0.0    # [-0.35, +0.35] rad


class FlightDynamics6DOF:
    """
    6 Serbestlik Dereceli Non-Lineer Aerodinamik Uçuş Simülatörü.
    """

    GRAVITY = 9.80665
    AIR_DENSITY = 1.225

    def __init__(self, params: Optional[AircraftAeroParams] = None, initial_state: Optional[AircraftState6DOF] = None):
        self.params = params or AircraftAeroParams()
        self.state = initial_state or AircraftState6DOF()

    def step(self, controls: ControlInputs, wind_ned: Tuple[float, float, float] = (0.0, 0.0, 0.0), dt: float = 0.02) -> AircraftState6DOF:
        """
        RK4 (Runge-Kutta 4. Derece) integrasyonu ile bir zaman adımı ilerletir.
        """
        # RK4 adımları
        k1 = self._compute_derivatives(self.state, controls, wind_ned)
        
        s2 = self._add_state_derivative(self.state, k1, dt * 0.5)
        k2 = self._compute_derivatives(s2, controls, wind_ned)
        
        s3 = self._add_state_derivative(self.state, k2, dt * 0.5)
        k3 = self._compute_derivatives(s3, controls, wind_ned)
        
        s4 = self._add_state_derivative(self.state, k3, dt)
        k4 = self._compute_derivatives(s4, controls, wind_ned)

        # Ağırlıklı türev toplamı: (k1 + 2*k2 + 2*k3 + k4) / 6
        final_deriv = [
            (k1[i] + 2.0 * k2[i] + 2.0 * k3[i] + k4[i]) / 6.0
            for i in range(12)
        ]

        self.state = self._add_state_derivative(self.state, final_deriv, dt)

        # Zemin temas kısıtlaması (pos_d > 0 ise zemin çarpması)
        if self.state.pos_d > 0.0:
            self.state.pos_d = 0.0
            self.state.w = 0.0
            self.state.q = 0.0
            self.state.p = 0.0

        return self.state

    def _compute_derivatives(self, s: AircraftState6DOF, c: ControlInputs, wind_ned: Tuple[float, float, float]) -> list:
        """
        Durum vektörü türevlerini hesaplar: [d_pos_n, d_pos_e, d_pos_d, du, dv, dw, dphi, dtheta, dpsi, dp, dq, dr]
        """
        p_par = self.params
        g = self.GRAVITY
        rho = self.AIR_DENSITY

        # 1. Rüzgar dönüşümü: NED rüzgarını gövde eksenine çevir
        R_b_ned = self._rotation_ned_to_body(s.phi, s.theta, s.psi)
        wind_body = self._mat_vec_mult(R_b_ned, [wind_ned[0], wind_ned[1], wind_ned[2]])

        # Bağıl hava hızları
        u_air = s.u - wind_body[0]
        v_air = s.v - wind_body[1]
        w_air = s.w - wind_body[2]
        airspeed = max(math.sqrt(u_air * u_air + v_air * v_air + w_air * w_air), 0.1)

        # 2. Aerodinamik açılar
        alpha = math.atan2(w_air, max(u_air, 0.1))
        beta = math.asin(max(-1.0, min(1.0, v_air / airspeed)))
        q_bar = 0.5 * rho * airspeed * airspeed

        # 3. Boyutsuz katsayılar
        cl = p_par.cl_0 + p_par.cl_alpha * alpha + p_par.cl_delta_e * c.elevator_rad
        cd = p_par.cd_0 + p_par.induced_drag_k * (cl * cl)
        cy = p_par.cy_beta * beta + p_par.cy_delta_r * c.rudder_rad

        # Moment katsayıları
        c_bar = p_par.mean_chord_m
        b = p_par.wing_span_m

        # Boyutsuz açısal hızlar
        q_hat = (s.q * c_bar) / (2.0 * airspeed)
        p_hat = (s.p * b) / (2.0 * airspeed)
        r_hat = (s.r * b) / (2.0 * airspeed)

        cm = p_par.cm_0 + p_par.cm_alpha * alpha + p_par.cm_q * q_hat + p_par.cm_delta_e * c.elevator_rad
        cl_roll = p_par.cl_beta * beta + p_par.cl_p * p_hat + p_par.cl_delta_a * c.aileron_rad
        cn = p_par.cn_beta * beta + p_par.cn_r * r_hat + p_par.cn_delta_r * c.rudder_rad

        # 4. Aerodinamik Kuvvetler (Stabilite ekseninden gövdeye)
        lift = q_bar * p_par.wing_area_m2 * cl
        drag = q_bar * p_par.wing_area_m2 * cd
        sideforce = q_bar * p_par.wing_area_m2 * cy

        cos_a = math.cos(alpha)
        sin_a = math.sin(alpha)

        # Gövde ekseni aerodinamik kuvvetleri
        fx_aero = -drag * cos_a + lift * sin_a
        fy_aero = sideforce
        fz_aero = -drag * sin_a - lift * cos_a

        # İtki kuvveti (Gövde +X ekseninde)
        thrust = max(0.0, min(1.0, c.throttle)) * p_par.max_thrust_n

        # Toplam gövde kuvvetleri
        fx = fx_aero + thrust
        fy = fy_aero
        fz = fz_aero

        # Aerodinamik Momentler
        l_moment = q_bar * p_par.wing_area_m2 * b * cl_roll
        m_moment = q_bar * p_par.wing_area_m2 * c_bar * cm
        n_moment = q_bar * p_par.wing_area_m2 * b * cn

        # 5. Translasiyonel Hareket Denklemleri (Gövde ivmeleri)
        m = p_par.mass_kg
        sin_t = math.sin(s.theta)
        cos_t = math.cos(s.theta)
        sin_p = math.sin(s.phi)
        cos_p = math.cos(s.phi)

        du = s.r * s.v - s.q * s.w - g * sin_t + (fx / m)
        dv = s.p * s.w - s.r * s.u + g * cos_t * sin_p + (fy / m)
        dw = s.q * s.u - s.p * s.v + g * cos_t * cos_p + (fz / m)

        # Kinematik: Gövde hızından NED hızına (R_ned_b)
        R_ned_b = self._mat_transpose(R_b_ned)
        vel_ned = self._mat_vec_mult(R_ned_b, [s.u, s.v, s.w])
        d_pos_n = vel_ned[0]
        d_pos_e = vel_ned[1]
        d_pos_d = vel_ned[2]

        # 6. Rotasyonel Hareket Denklemleri (Euler açısal ivmeleri)
        dp = l_moment / p_par.ixx
        dq = m_moment / p_par.iyy
        dr = n_moment / p_par.izz

        # Açısal kinematik: [p, q, r] -> [dphi, dtheta, dpsi]
        tan_t = math.tan(s.theta) if abs(cos_t) > 1e-4 else 0.0
        sec_t = 1.0 / cos_t if abs(cos_t) > 1e-4 else 1.0

        dphi = s.p + (s.q * sin_p + s.r * cos_p) * tan_t
        dtheta = s.q * cos_p - s.r * sin_p
        dpsi = (s.q * sin_p + s.r * cos_p) * sec_t

        return [
            d_pos_n, d_pos_e, d_pos_d,
            du, dv, dw,
            dphi, dtheta, dpsi,
            dp, dq, dr
        ]

    @staticmethod
    def _add_state_derivative(s: AircraftState6DOF, d: list, dt: float) -> AircraftState6DOF:
        return AircraftState6DOF(
            pos_n=s.pos_n + d[0] * dt,
            pos_e=s.pos_e + d[1] * dt,
            pos_d=s.pos_d + d[2] * dt,
            u=s.u + d[3] * dt,
            v=s.v + d[4] * dt,
            w=s.w + d[5] * dt,
            phi=s.phi + d[6] * dt,
            theta=s.theta + d[7] * dt,
            psi=s.psi + d[8] * dt,
            p=s.p + d[9] * dt,
            q=s.q + d[10] * dt,
            r=s.r + d[11] * dt
        )

    @staticmethod
    def _rotation_ned_to_body(phi: float, theta: float, psi: float) -> list:
        cp = math.cos(phi)
        sp = math.sin(phi)
        ct = math.cos(theta)
        st = math.sin(theta)
        cy = math.cos(psi)
        sy = math.sin(psi)

        return [
            [ct * cy, ct * sy, -st],
            [sp * st * cy - cp * sy, sp * st * sy + cp * cy, sp * ct],
            [cp * st * cy + sp * sy, cp * st * sy - sp * cy, cp * ct]
        ]

    @staticmethod
    def _mat_vec_mult(mat: list, vec: list) -> list:
        return [
            mat[0][0] * vec[0] + mat[0][1] * vec[1] + mat[0][2] * vec[2],
            mat[1][0] * vec[0] + mat[1][1] * vec[1] + mat[1][2] * vec[2],
            mat[2][0] * vec[0] + mat[2][1] * vec[1] + mat[2][2] * vec[2]
        ]

    @staticmethod
    def _mat_transpose(mat: list) -> list:
        return [
            [mat[0][0], mat[1][0], mat[2][0]],
            [mat[0][1], mat[1][1], mat[2][1]],
            [mat[0][2], mat[1][2], mat[2][2]]
        ]
