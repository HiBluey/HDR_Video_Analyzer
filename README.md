# HDR Analyzer Pro 📊

![Python](https://img.shields.io/badge/Python-3.8%2B-blue)
![FFmpeg](https://img.shields.io/badge/Dependency-FFmpeg-green)
![License](https://img.shields.io/badge/license-MIT-grey)

**HDR Analyzer Pro** is a high-performance Python tool designed to analyze brightness (Nits) and color gamut coverage (Rec.709 / P3 / Rec.2020) of HDR video files.

Unlike typical analyzers that rely on slow RGB conversions or incorrect scaling, this tool uses **native 10-bit YUV 4:2:0 reading** combined with **NumPy vectorization** to deliver industrial-grade accuracy and speed.

## 🚀 Key Features

* **Native Performance**: Reads raw `yuv420p10le` data directly from FFmpeg pipes, reducing I/O bandwidth by 50% compared to RGB conversion methods.
* **Ultrafast Subsampling**: Optional "Subsampling Mode" (physical slicing `[::2, ::2]`) processes 4K video at 1080p speeds without interpolation ringing or peak brightness loss.
* **Strict 16:9 Logic**: Automatically pads videos (e.g., 2.35:1 movies) to a standard 3840x2160 16:9 canvas with black bars, ensuring "Average Nits" calculations align with standard display definitions.
* **Advanced Color Science**:
    * Implements SMPTE ST 2084 (PQ) EOTF curve.
    * Uses Rec.2020 luminance coefficients.
    * **Dual-Threshold Noise Filter**: Filters out sensor noise in dark scenes using both Luminance ($Y \ge 1.0$ nits) and Color Energy ($X+Y+Z > 0.005$) thresholds to prevent false "Out-of-Gamut" readings.
* **Visualization**: Generates professional dual-chart reports (Brightness Waveform + Gamut Stacked Plot).
* **Re-plot Capable**: Can import existing `.csv` files to adjust charts without re-analyzing the video.

## 🛠️ Requirements

* **Python 3.x**
* **FFmpeg** (Must be installed and added to your system `PATH`).
* Python Libraries:
    ```bash
    pip install numpy matplotlib
    ```
    *(Tkinter is usually included with Python)*

## 📖 Usage

1.  **Run the script**:
    ```bash
    python HDR_Analyzer_Pro_v9.py
    ```
2.  **Select Mode**:
    * **Analyze New Video**: Choose a 4K HDR video file (MKV, MP4, TS).
    * **Plot from CSV**: Select a previously generated `.csv` to re-draw charts.
3.  **Configure Settings**:
    * **Sampling Interval**: Choose between Frame-by-frame (Slowest), 1s/sample, or 2s/sample.
    * **Subsampling**: 
        * `Yes`: Fast mode (Recommended). Physical pixel skipping. No interpolation artifacts.
        * `No`: Full pixel analysis.
4.  **Result**: 
    * A `.csv` file containing timestamped Nits and Gamut data.
    * A `.png` chart visualizing the analysis.

## 📊 Output Explanation

The tool generates a CSV and a Chart with two sections:

1.  **Brightness (Top Chart)**:
    * **Peak Nits**: The maximum brightness of the brightest pixel in the frame (or sampled area).
    * **Avg Nits**: The average brightness of the entire 16:9 frame (including black bars).
    * *Axis is plotted in PQ space but labeled in Nits.*

2.  **Gamut Ratio (Bottom Chart)**:
    * **Rec.709 / Dark**: Pixels that are either dark (< 1.0 nits), low confidence, or within the standard Rec.709 triangle.
    * **P3**: Pixels that exceed Rec.709 but fall within DCI-P3.
    * **Rec.2020**: Pixels that exceed DCI-P3 boundaries.

## ⚙️ Technical Details

### Why "Pad to 16:9"?
Averages calculated on cropped frames (e.g., 3840x1600) are artificially inflated. By padding to 3840x2160, this tool provides standardized metrics comparable across different aspect ratios.

### The "Confidence Filter"
Dark scenes in HDR often contain sensor noise. A simple brightness threshold isn't enough. This tool applies a secondary check on the total XYZ energy. If a pixel is "bright" but has extremely low chromatic energy, it is treated as noise (Rec.709) rather than false high-saturation color.

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
