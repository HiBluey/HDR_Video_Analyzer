import sys, os, csv, subprocess, traceback
import shutil
import tkinter as tk
from tkinter import filedialog, messagebox
import numpy as np
import matplotlib.pyplot as plt

# --- 核心色彩科学常量 ---
# Rec.2020 到 XYZ 的转换矩阵
M_2020_to_XYZ = np.array([
    [0.636958, 0.144617, 0.168881],
    [0.262700, 0.677998, 0.059302],
    [0.049461, 0.028665, 1.092973]
])
# Rec.2020 亮度系数
Y_COEFF = np.array([0.262700, 0.677998, 0.059302])

# 色域顶点 (CIE xy)
GAMUT_709 = np.array([[0.64, 0.33], [0.30, 0.60], [0.15, 0.06]])
GAMUT_P3  = np.array([[0.68, 0.32], [0.265, 0.69], [0.15, 0.06]])

# PQ EOTF Constants (ST 2084)
m1, m2 = 2610./16384., 2523./4096.*128.
c1, c2, c3 = 3424./4096., 2413./4096.*32., 2392./4096.*32.

def pq_eotf(norm_val):
    """将归一化的 PQ 信号 (0-1) 转换为线性光 (0-1)"""
    val = np.power(np.maximum(norm_val, 0), 1.0/m2)
    num = np.maximum(val - c1, 0)
    den = c2 - c3 * val
    return np.power(num / den, 1.0/m1)

def pq_inverse(nits):
    """将 Nits 转换为 PQ 信号值 (仅用于绘图坐标轴)"""
    y = np.clip(nits / 10000.0, 1e-10, 1.0)
    v = np.power(y, m1)
    return np.power((c1 + c2 * v) / (1 + c3 * v), m2)

def is_in_gamut(xy, vertices):
    """判断 xy 坐标是否落在指定三角形色域内 (向量法)"""
    a, b, c = vertices
    v0, v1, v2 = c - a, b - a, xy - a
    invDenom = 1.0 / (np.dot(v0, v0) * np.dot(v1, v1) - np.dot(v0, v1) * np.dot(v0, v1))
    u = (np.dot(v1, v1) * np.sum(v2 * v0, axis=1) - np.dot(v0, v1) * np.sum(v2 * v1, axis=1)) * invDenom
    v = (np.dot(v0, v0) * np.sum(v2 * v1, axis=1) - np.dot(v0, v1) * np.sum(v2 * v0, axis=1)) * invDenom
    return (u >= 0) & (v >= 0) & (u + v <= 1)

# --- 绘图逻辑 ---
def plot_from_csv(csv_path):
    try:
        data = np.genfromtxt(csv_path, delimiter=',', skip_header=1)
        if data.ndim == 1: data = data.reshape(1, -1)
        t, peak, avg, r709, rp3, r2020 = data.T
        
        # 移除全局 sharex=True，因为图1图2的X轴是时间，而图3的X轴是APL百分比
        fig, (ax1, ax2, ax3) = plt.subplots(3, 1, figsize=(14, 13))
        ax2.sharex(ax1) # 仅让图2共享图1的时间轴
        plt.setp(ax1.get_xticklabels(), visible=False) # 隐藏图1的刻度以保持整洁
        plt.subplots_adjust(hspace=0.2)
        fig.suptitle(f"HDR Analysis: {os.path.basename(csv_path)}", fontsize=12)

        # 图 1: 亮度 (PQ 坐标轴)
        y_ticks = [0, 0.1, 1, 10, 50, 100, 203, 500, 1000, 4000, 10000]
        ax1.plot(t, [pq_inverse(p) for p in peak], color='#FF8C00', lw=0.8, label='Peak (Nits)')
        ax1.plot(t, [pq_inverse(a) for a in avg], color='#1E90FF', lw=0.8, label='Avg (Nits)')
        ax1.set_yticks([pq_inverse(y) for y in y_ticks])
        ax1.set_yticklabels(y_ticks)
        ax1.set_ylim(0, 1)
        ax1.set_ylabel('Brightness (Nits)')
        ax1.grid(True, alpha=0.2)
        ax1.legend(loc='upper right')

        # 添加四个亮度统计值 (已修改为移至右下角)
        max_cll = np.max(peak)
        ave_cll = np.mean(peak)
        max_fall = np.max(avg)
        ave_fall = np.mean(avg)
        
        stats_text = (f"MaxCLL: {max_cll:.0f} nits\n"
                      f"AveCLL: {ave_cll:.0f} nits\n"
                      f"MaxFALL: {max_fall:.0f} nits\n"
                      f"AveFALL: {ave_fall:.0f} nits")
        
        ax1.text(0.99, 0.04, stats_text, transform=ax1.transAxes,
                 fontsize=10, verticalalignment='bottom', horizontalalignment='right',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='#CCCCCC'))

        # 图 2: 色域占比
        ax2.stackplot(t, r709, rp3, r2020, colors=['#BBBBBB', '#F4D03F', '#E74C3C'], 
                      labels=['Rec.709', 'P3 (outside 709)', 'Rec.2020 (outside P3)'])
        ax2.set_ylim(0, 1)
        ax2.set_ylabel('Gamut Ratio')
        ax2.set_xlabel('Time (s)')
        ax2.legend(loc='lower left')
        
        # --- 图 3: APL 百分比分布直方图 (已强制默认使用 PQ 码值方式 2) ---
        apl_data = np.array([pq_inverse(a) for a in avg]) * 100.0
        apl_xlabel = 'APL (%)'
            
        # 绘制直方图 (横轴0-100%，分为100个柱子)
        ax3.hist(apl_data, bins=100, range=(0, 100), color='#32CD32', alpha=0.7, edgecolor='white', linewidth=0.5)
        ax3.set_xlim(0, 100)
        ax3.set_xlabel(apl_xlabel)
        ax3.set_ylabel('Frame Count')
        ax3.grid(True, alpha=0.2)
        
        # 计算并添加平均数和中位数统计 (右下角)
        mean_apl = np.mean(apl_data)
        median_apl = np.median(apl_data)
        
        stats_text_apl = (f"Average APL: {mean_apl:.2f}%\n"
                          f"Median APL: {median_apl:.2f}%")
        
        ax3.text(0.99, 0.04, stats_text_apl, transform=ax3.transAxes,
                 fontsize=10, verticalalignment='bottom', horizontalalignment='right',
                 bbox=dict(boxstyle='round,pad=0.5', facecolor='white', alpha=0.8, edgecolor='#CCCCCC'))
        
        save_img = csv_path.replace('.csv', '.png')
        plt.savefig(save_img, dpi=150)
        print(f"\n[完成] 图表已保存至: {save_img}")
        plt.show()
    except Exception as e:
        messagebox.showerror("绘图错误", f"解析 CSV 失败: {e}")

# --- 核心分析逻辑 ---
def run_main():
    root = tk.Tk(); root.withdraw()
    
    # 1. 模式选择
    choice = messagebox.askyesnocancel("HDR 分析仪 Pro", 
                                       "点击【是 (Yes)】：分析新视频\n"
                                       "点击【否 (No)】：仅导入 CSV 绘图\n"
                                       "点击【取消】：退出")
    if choice is None: return 
    
    if choice is False: # 仅绘图
        c_path = filedialog.askopenfilename(title="选择 CSV 文件", filetypes=[("CSV Files", "*.csv")])
        if c_path: 
            # 直接调用绘图，删除了询问 APL 模式的弹窗
            plot_from_csv(c_path)
        return

    # 2. 视频分析设置
    v_path = filedialog.askopenfilename(title="选择 HDR 视频 (4K)", 
                                        filetypes=[("Video Files", "*.mkv *.mp4 *.mov *.ts"), ("All Files", "*.*")])
    if not v_path: return
    if v_path.lower().endswith('.csv'):
        messagebox.showerror("错误", "不能选择 CSV 文件！请选择视频文件。"); return
    
    # --- FFmpeg 依赖检查 ---
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        messagebox.showerror(
            "缺少核心依赖", 
            "系统未检测到 FFmpeg！\n\n"
            "本软件依赖 FFmpeg 进行视频解码。\n"
            "请确保您已下载 FFmpeg 并将其 bin 目录添加到了系统的环境变量 (PATH) 中。"
        )
        return

    # 删除了 tkinter.simpledialog 的导入和调用，将步骤改为 1/2 和 2/2
    from tkinter import simpledialog

    # 参数 1: 采样间隔 (修改提示文字配合 2 个步骤)
    sample_mode = simpledialog.askstring("步骤 1/2: 采样间隔", 
                                       "1: 逐帧 (极慢)\n2: 1秒/次 (推荐)\n3: 2秒/次", initialvalue="2")
    fps_val = {"1": "0", "2": "1", "3": "0.5"}.get(sample_mode, "1")

    # 参数 2: 隔点采样 (速度优化)
    use_subsample = messagebox.askyesno("步骤 2/2: 速度优化", 
                                      "是否启用隔点采样 (Subsampling)?\n\n"
                                      "【是 (Yes)】: 读取4K后每隔1个点采一次样 (相当于1080P数据量)。\n"
                                      "   优点: 速度快4倍，无插值振铃，峰值亮度精准。\n\n"
                                      "【否 (No)】: 全像素分析 (830万像素/帧)。\n"
                                      "   优点: 数据密度最大。\n"
                                      "   缺点: 速度较慢。")

    # 删除了原有的“步骤 3/3” (APL 计算设置)

    try:
        # Windows 隐藏控制台
        startupinfo = subprocess.STARTUPINFO()
        startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
        
        # 获取时长
        dur_cmd = ['ffprobe', '-v', '0', '-show_entries', 'format=duration', '-of', 'csv=p=0', v_path]
        total_duration = float(subprocess.check_output(dur_cmd, startupinfo=startupinfo).decode().strip())
        
        # 构建 FFmpeg 命令
        filters = [f"pad=3840:2160:(ow-iw)/2:(oh-ih)/2:black"]
        if fps_val != "0": filters.insert(0, f"fps={fps_val}")
        
        cmd = ['ffmpeg', '-i', v_path, '-vf', ",".join(filters), '-pix_fmt', 'gbrp10le', '-f', 'rawvideo', 'pipe:1']
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, startupinfo=startupinfo)
        
        # 4K 10bit buffer size
        width_4k, height_4k = 3840, 2160
        frame_bytes = width_4k * height_4k * 3 * 2
        
        results = []
        idx = 0
        t_step = 1.0 if fps_val=="1" else (2.0 if fps_val=="0.5" else 0.0416)

        print(f"\n>>> 开始分析: {os.path.basename(v_path)}")
        print(f"    模式: 4K 原生 {'(隔点采样)' if use_subsample else '(全像素)'}")
        print("-" * 60)

        while True:
            data = proc.stdout.read(frame_bytes)
            if not data: break
            
            # 1. 读取原始 4K 数据
            raw = np.frombuffer(data, dtype=np.uint16).reshape((3, height_4k, width_4k))
            
            # 2. 采样策略
            if use_subsample:
                process_data = raw[:, ::2, ::2]
            else:
                process_data = raw

            # 3. 归一化 & PQ 转换
            rgb = np.stack([process_data[2], process_data[0], process_data[1]], axis=-1).astype(np.float32) / 1023.0
            lin_rgb = pq_eotf(rgb)
            
            # 4. 亮度计算 (使用全画面数据，分母含黑边)
            nits_map = np.dot(lin_rgb, Y_COEFF) * 10000.0
            peak = np.max(nits_map)
            avg = np.mean(nits_map)
            
            # 5. 色域计算 (双重去噪逻辑)
            total_px = nits_map.size
            
            mask_bright = nits_map >= 1.0
            bright_lin = lin_rgb[mask_bright]
            
            if bright_lin.size > 0:
                xyz = bright_lin @ M_2020_to_XYZ.T
                
                s = np.sum(xyz, axis=1, keepdims=True)
                confidence_mask = s.flatten() > 0.000
                
                s[s == 0] = 1e-6
                xy = xyz[:, :2] / s
                
                in_709 = is_in_gamut(xy, GAMUT_709)
                in_p3 = is_in_gamut(xy, GAMUT_P3)
                
                valid_in_709 = np.ones(len(xy), dtype=bool)
                valid_in_p3 = np.ones(len(xy), dtype=bool)
                
                valid_in_709[confidence_mask] = in_709[confidence_mask]
                valid_in_p3[confidence_mask] = in_p3[confidence_mask]
                
                c709 = np.sum(valid_in_709) + (total_px - bright_lin.shape[0])
                cp3 = np.sum(valid_in_p3 & ~valid_in_709)
                c2020 = bright_lin.shape[0] - np.sum(valid_in_p3)
                
                r709, rp3, r2020 = c709/total_px, cp3/total_px, c2020/total_px
            else:
                r709, rp3, r2020 = 1.0, 0.0, 0.0

            results.append([idx * t_step, peak, avg, r709, rp3, r2020])
            
            # 进度条
            progress = (idx * t_step) / total_duration * 100
            sys.stdout.write(f"\r进度: [{progress:>5.1f}%] | Time: {idx*t_step:>6.1f}s | Peak: {peak:>5.0f} nits")
            sys.stdout.flush() 
            idx += 1

        csv_fn = v_path + ".analysis.csv"
        with open(csv_fn, 'w', newline='') as f:
            csv.writer(f).writerows([['Time','Peak','Avg','R709','RP3','R2020']] + results)
        
        print(f"\n\n分析完成！CSV 已保存。\n正在生成图表...")
        plot_from_csv(csv_fn)

    except Exception:
        messagebox.showerror("运行出错", traceback.format_exc())
    finally:
        root.destroy()

if __name__ == "__main__":
    run_main()
