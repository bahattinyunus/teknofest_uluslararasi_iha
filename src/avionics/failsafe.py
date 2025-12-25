"""
UAV-Architect-Global: Avionics & Failsafe
-----------------------------------------
Donanım kontrol ve acil durum protokolleri.
"""

class AvionicsController:
    def __init__(self):
        self.failsafe_active = False

    def trigger_rtl(self):
        """Return to Launch (RTL) protocol"""
        print("[AVIONICS] CRITICAL: Triggering RTL Protocol...")
        self.failsafe_active = True

    def monitor_power(self, voltage):
        if voltage < 14.8:  # Example: 4S LiPo low voltage
            self.trigger_rtl()
