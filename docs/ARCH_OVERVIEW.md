# System Architecture Deep Dive

## High-Level Vision
The **UAV-Architect-Global** system is designed based on the **Observer-Executor** pattern. The companion computer (Observer) processes high-bandwidth data (video, LiDAR), while the flight controller (Executor) handles real-time stabilization.

## Data Flow
1. **Sensors** transmit RAW data to the CPU/GPU.
2. **AI Inference** (YOLO) identifies targets.
3. **Mission Logic** determines if parameters for payload release are met.
4. **MavLink Commands** are sent to the Pixhawk to adjust pitch/yaw or trigger servos.

## Integration Protocols
- **Baud Rate:** 57600/921600 (Depending on distance).
- **Latency Target:** < 50ms for end-to-end processing.

---
*Prepared by Bahattin Yunus Çetin*
