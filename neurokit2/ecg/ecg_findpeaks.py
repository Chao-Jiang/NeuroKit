# - * - coding: utf-8 - * -

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
import scipy.signal

from ..signal import signal_smooth
from ..signal import signal_formatpeaks



def ecg_findpeaks(ecg_cleaned, sampling_rate=1000, method="neurokit", show=False):
    """Find R-peaks in an ECG signal.

    Low-level function used by `ecg_peaks()` to identify R-peaks in an ECG signal using a different set of algorithms. See `ecg_peaks()` for details.

    Parameters
    ----------
    ecg_cleaned : list, array or Series
        The cleaned ECG channel as returned by `ecg_clean()`.
    sampling_rate : int
        The sampling frequency of `ecg_signal` (in Hz, i.e., samples/second).
        Defaults to 1000.
    method : string
        The algorithm to be used for R-peak detection. Can be one of 'neurokit' (default),
        'pamtompkins1985', 'hamilton2002', 'christov2004', 'gamboa2008', 'elgendi2010',
        'engzeemod2012' or 'kalidas2017'.
    show : bool
        If True, will return a plot to visualizing the thresholds used in the
        algorithm. Useful for debugging.

    Returns
    -------
    info : dict
        A dictionary containing additional information, in this case the
        samples at which R-peaks occur, accessible with the key "ECG_R_Peaks".

    See Also
    --------
    ecg_clean, ecg_fixpeaks, ecg_peaks, ecg_rate, ecg_process, ecg_plot

    Examples
    --------
    >>> import neurokit2 as nk
    >>>
    >>> ecg = nk.ecg_simulate(duration=10, sampling_rate=1000)
    >>> cleaned = nk.ecg_clean(ecg, sampling_rate=1000)
    >>> info = nk.ecg_findpeaks(cleaned)
    >>> nk.events_plot(info["ECG_R_Peaks"], cleaned)
    >>>
    >>> # Different methods
    >>> neurokit = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="neurokit"), method="neurokit")
    >>> pantompkins1985 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="pantompkins1985"), method="pantompkins1985")
    >>> hamilton2002 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="hamilton2002"), method="hamilton2002")
    >>> christov2004 = nk.ecg_findpeaks(ecg, method="christov2004")
    >>> gamboa2008 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="gamboa2008"), method="gamboa2008")
    >>> elgendi2010 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="elgendi2010"), method="elgendi2010")
    >>> engzeemod2012 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="engzeemod2012"), method="engzeemod2012")
    >>> kalidas2017 = nk.ecg_findpeaks(nk.ecg_clean(ecg, method="kalidas2017"), method="kalidas2017")
    >>>
    >>> # Visualize
    >>> nk.events_plot([neurokit["ECG_R_Peaks"],
                        pantompkins1985["ECG_R_Peaks"],
                        hamilton2002["ECG_R_Peaks"],
                        christov2004["ECG_R_Peaks"],
                        gamboa2008["ECG_R_Peaks"],
                        elgendi2010["ECG_R_Peaks"],
                        engzeemod2012["ECG_R_Peaks"],
                        kalidas2017["ECG_R_Peaks"]], cleaned)

    References
    --------------
    - Gamboa, H. (2008). Multi-modal behavioral biometrics based on hci and electrophysiology. PhD ThesisUniversidade.
    - W. Zong, T. Heldt, G.B. Moody, and R.G. Mark. An open-source algorithm to detect onset of arterial blood pressure pulses. In Computers in Cardiology, 2003, pages 259–262, 2003.
    - Hamilton, Open Source ECG Analysis Software Documentation, E.P.Limited, 2002.
    - Jiapu Pan and Willis J. Tompkins. A Real-Time QRS Detection Algorithm. In: IEEE Transactions on Biomedical Engineering BME-32.3 (1985), pp. 230–236.
    - C. Zeelenberg, A single scan algorithm for QRS detection and feature extraction, IEEE Comp. in Cardiology, vol. 6, pp. 37-42, 1979
    - A. Lourenco, H. Silva, P. Leite, R. Lourenco and A. Fred, "Real Time Electrocardiogram Segmentation for Finger Based ECG Biometrics", BIOSIGNALS 2012, pp. 49-54, 2012.
    """
    # Try retrieving right column
    if isinstance(ecg_cleaned, pd.DataFrame):
        try:
            ecg_cleaned = ecg_cleaned["ECG_Clean"]
        except NameError:
            try:
                ecg_cleaned = ecg_cleaned["ECG_Raw"]
            except NameError:
                ecg_cleaned = ecg_cleaned["ECG"]


    method = method.lower()  # remove capitalised letters
    # Run peak detection algorithm
    if method in ["nk", "nk2", "neurokit", "neurokit2"]:
        rpeaks = _ecg_findpeaks_neurokit(ecg_cleaned, sampling_rate,
                                         show=show)
    elif method in ["pantompkins", "pantompkins1985"]:
        rpeaks = _ecg_findpeaks_pantompkins(ecg_cleaned, sampling_rate)
    elif method in ["gamboa2008", "gamboa"]:
        rpeaks = _ecg_findpeaks_gamboa(ecg_cleaned, sampling_rate)
    elif method in ["ssf", "slopesumfunction", "zong", "zong2003"]:
        rpeaks = _ecg_findpeaks_ssf(ecg_cleaned, sampling_rate)
    elif method in ["hamilton", "hamilton2002"]:
        rpeaks = _ecg_findpeaks_hamilton(ecg_cleaned, sampling_rate)
    elif method in ["christov", "christov2004"]:
        rpeaks = _ecg_findpeaks_christov(ecg_cleaned, sampling_rate)
    elif method in ["engzee", "engzee2012", "engzeemod", "engzeemod2012"]:
        rpeaks = _ecg_findpeaks_engzee(ecg_cleaned, sampling_rate)
    elif method in ["elgendi", "elgendi2010"]:
        rpeaks = _ecg_findpeaks_elgendi(ecg_cleaned, sampling_rate)
    elif method in ["kalidas2017", "swt", "kalidas", "kalidastamil", "kalidastamil2017"]:
        rpeaks = _ecg_findpeaks_kalidas(ecg_cleaned, sampling_rate)
    else:
        raise ValueError("NeuroKit error: ecg_findpeaks(): 'method' should be "
                         "one of 'neurokit' or 'pamtompkins'.")


    # Prepare output.
    info = {"ECG_R_Peaks": rpeaks}

    return info





# =============================================================================
# NeuroKit
# =============================================================================
def _ecg_findpeaks_neurokit(signal, sampling_rate=1000, smoothwindow=.1, avgwindow=.75,
                            gradthreshweight=1.5, minlenweight=0.4, mindelay=0.3,
                            show=False):
    """
    All tune-able parameters are specified as keyword arguments. The `signal`
    must be the highpass-filtered raw ECG with a lowcut of .5 Hz.
    """
    if show is True:
        fig, (ax1, ax2) = plt.subplots(nrows=2, ncols=1, sharex=True)

    # Compute the ECG's gradient as well as the gradient threshold. Run with
    # show=True in order to get an idea of the threshold.
    grad = np.gradient(signal)
    absgrad = np.abs(grad)
    smooth_kernel = int(np.rint(smoothwindow * sampling_rate))
    avg_kernel = int(np.rint(avgwindow * sampling_rate))
    smoothgrad = signal_smooth(absgrad, kernel="boxcar", size=smooth_kernel)
    avggrad = signal_smooth(smoothgrad, kernel="boxcar", size=avg_kernel)
    gradthreshold = gradthreshweight * avggrad
    mindelay = int(np.rint(sampling_rate * mindelay))

    if show is True:
        ax1.plot(signal)
        ax2.plot(smoothgrad)
        ax2.plot(gradthreshold)

    # Identify start and end of QRS complexes.
    qrs = smoothgrad > gradthreshold
    beg_qrs = np.where(np.logical_and(np.logical_not(qrs[0:-1]), qrs[1:]))[0]
    end_qrs = np.where(np.logical_and(qrs[0:-1], np.logical_not(qrs[1:])))[0]
    # Throw out QRS-ends that precede first QRS-start.
    end_qrs = end_qrs[end_qrs > beg_qrs[0]]

    # Identify R-peaks within QRS (ignore QRS that are too short).
    num_qrs = min(beg_qrs.size, end_qrs.size)
    min_len = np.mean(end_qrs[:num_qrs] - beg_qrs[:num_qrs]) * minlenweight
    peaks = [0]

    for i in range(num_qrs):

        beg = beg_qrs[i]
        end = end_qrs[i]
        len_qrs = end - beg

        if len_qrs < min_len:
            continue

        if show is True:
            ax2.axvspan(beg, end, facecolor="m", alpha=0.5)

        # Find local maxima and their prominence within QRS.
        data = signal[beg:end]
        locmax, props = scipy.signal.find_peaks(data, prominence=(None, None))

        if locmax.size > 0:
            # Identify most prominent local maximum.
            peak = beg + locmax[np.argmax(props["prominences"])]
            # Enforce minimum delay between peaks.
            if peak - peaks[-1] > mindelay:
                peaks.append(peak)

    peaks.pop(0)

    if show is True:
        ax1.scatter(peaks, signal[peaks], c="r")

    peaks = np.asarray(peaks).astype(int)  # Convert to int
    return peaks




# =============================================================================
# Pan & Tompkins (1985)
# =============================================================================
def _ecg_findpeaks_pantompkins(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - Jiapu Pan and Willis J. Tompkins. A Real-Time QRS Detection Algorithm.
    In: IEEE Transactions on Biomedical Engineering BME-32.3 (1985), pp. 230–236.
    """
    diff = np.diff(signal)

    squared = diff * diff

    N = int(0.12 * sampling_rate)
    mwa = _ecg_findpeaks_MWA(squared, N)
    mwa[:int(0.2 * sampling_rate)] = 0

    mwa_peaks = _ecg_findpeaks_peakdetect(mwa, sampling_rate)

    mwa_peaks = np.array(mwa_peaks, dtype='int')
    return mwa_peaks



# =============================================================================
# Hamilton (2002)
# =============================================================================
def _ecg_findpeaks_hamilton(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - Hamilton, Open Source ECG Analysis Software Documentation, E.P.Limited, 2002.
    """
    diff = abs(np.diff(signal))

    b = np.ones(int(0.08 * sampling_rate))
    b = b/int(0.08 * sampling_rate)
    a = [1]

    ma = scipy.signal.lfilter(b, a, diff)

    ma[0:len(b) * 2] = 0

    n_pks = []
    n_pks_ave = 0.0
    s_pks = []
    s_pks_ave = 0.0
    QRS = [0]
    RR = []
    RR_ave = 0.0

    th = 0.0

    i = 0
    idx = []
    peaks = []

    for i in range(len(ma)):

        if i > 0 and i < len(ma) - 1:
            if ma[i-1] < ma[i] and ma[i + 1] < ma[i]:
                peak = i
                peaks.append(i)

                if ma[peak] > th and (peak-QRS[-1]) > 0.3 * sampling_rate:
                    QRS.append(peak)
                    idx.append(i)
                    s_pks.append(ma[peak])
                    if len(n_pks) > 8:
                        s_pks.pop(0)
                    s_pks_ave = np.mean(s_pks)

                    if RR_ave != 0.0:
                        if QRS[-1]-QRS[-2] > 1.5 * RR_ave:
                            missed_peaks = peaks[idx[-2] + 1:idx[-1]]
                            for missed_peak in missed_peaks:
                                if missed_peak - peaks[idx[-2]] > int(0.360 * sampling_rate) and ma[missed_peak] > 0.5 * th:
                                    QRS.append(missed_peak)
                                    QRS.sort()
                                    break

                    if len(QRS) > 2:
                        RR.append(QRS[-1]-QRS[-2])
                        if len(RR) > 8:
                            RR.pop(0)
                        RR_ave = int(np.mean(RR))

                else:
                    n_pks.append(ma[peak])
                    if len(n_pks) > 8:
                        n_pks.pop(0)
                    n_pks_ave = np.mean(n_pks)

                th = n_pks_ave + 0.45 * (s_pks_ave-n_pks_ave)

                i += 1

    QRS.pop(0)

    QRS = np.array(QRS, dtype='int')
    return QRS


# =============================================================================
# Slope Sum Function (SSF) - Zong et al. (2003)
# =============================================================================
def _ecg_findpeaks_ssf(signal, sampling_rate=1000, threshold=20, before=0.03, after=0.01):
    """
    From https://github.com/PIA-Group/BioSPPy/blob/e65da30f6379852ecb98f8e2e0c9b4b5175416c3/biosppy/signals/ecg.py#L448

    - W. Zong, T. Heldt, G.B. Moody, and R.G. Mark. An open-source algorithm to detect onset of arterial blood pressure pulses. In Computers in
Cardiology, 2003, pages 259–262, 2003.
    """
    # TODO: Doesn't really seems to work

    # convert to samples
    winB = int(before * sampling_rate)
    winA = int(after * sampling_rate)

    Rset = set()
    length = len(signal)

    # diff
    dx = np.diff(signal)
    dx[dx >= 0] = 0
    dx = dx ** 2

    # detection
    idx, = np.nonzero(dx > threshold)
    idx0 = np.hstack(([0], idx))
    didx = np.diff(idx0)

    # search
    sidx = idx[didx > 1]
    for item in sidx:
        a = item - winB
        if a < 0:
            a = 0
        b = item + winA
        if b > length:
            continue

        r = np.argmax(signal[a:b]) + a
        Rset.add(r)

    # output
    rpeaks = list(Rset)
    rpeaks.sort()
    rpeaks = np.array(rpeaks, dtype='int')
    return rpeaks



# =============================================================================
# Christov (2004)
# =============================================================================
def _ecg_findpeaks_christov(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - Ivaylo I. Christov, Real time electrocardiogram QRS detection using combined adaptive threshold, BioMedical Engineering OnLine 2004, vol. 3:28, 2004.
    """
    total_taps = 0

    b = np.ones(int(0.02 * sampling_rate))
    b = b/int(0.02 * sampling_rate)
    total_taps += len(b)
    a = [1]

    MA1 = scipy.signal.lfilter(b, a, signal)

    b = np.ones(int(0.028 * sampling_rate))
    b = b/int(0.028 * sampling_rate)
    total_taps += len(b)
    a = [1]

    MA2 = scipy.signal.lfilter(b, a, MA1)

    Y = []
    for i in range(1, len(MA2)-1):

        diff = abs(MA2[i + 1]-MA2[i-1])

        Y.append(diff)

    b = np.ones(int(0.040 * sampling_rate))
    b = b/int(0.040 * sampling_rate)
    total_taps += len(b)
    a = [1]

    MA3 = scipy.signal.lfilter(b, a, Y)

    MA3[0:total_taps] = 0

    ms50 = int(0.05 * sampling_rate)
    ms200 = int(0.2 * sampling_rate)
    ms1200 = int(1.2 * sampling_rate)
    ms350 = int(0.35 * sampling_rate)

    M = 0
    newM5 = 0
    M_list = []
    MM = []
    M_slope = np.linspace(1.0, 0.6, ms1200-ms200)
    F = 0
    F_list = []
    R = 0
    RR = []
    Rm = 0
    R_list = []

    MFR = 0
    MFR_list = []

    QRS = []

    for i in range(len(MA3)):

        # M
        if i < 5 * sampling_rate:
            M = 0.6 * np.max(MA3[:i + 1])
            MM.append(M)
            if len(MM) > 5:
                MM.pop(0)

        elif QRS and i < QRS[-1] + ms200:
            newM5 = 0.6 * np.max(MA3[QRS[-1]:i])
            if newM5 > 1.5 * MM[-1]:
                newM5 = 1.1 * MM[-1]

        elif QRS and i == QRS[-1] + ms200:
            if newM5 == 0:
                newM5 = MM[-1]
            MM.append(newM5)
            if len(MM) > 5:
                MM.pop(0)
            M = np.mean(MM)

        elif QRS and i > QRS[-1] + ms200 and i < QRS[-1] + ms1200:

            M = np.mean(MM) * M_slope[i-(QRS[-1] + ms200)]

        elif QRS and i > QRS[-1] + ms1200:
            M = 0.6 * np.mean(MM)

        # F
        if i > ms350:
            F_section = MA3[i-ms350:i]
            max_latest = np.max(F_section[-ms50:])
            max_earliest = np.max(F_section[:ms50])
            F = F + ((max_latest-max_earliest)/150.0)

        # R
        if QRS and i < QRS[-1] + int((2.0/3.0 * Rm)):

            R = 0

        elif QRS and i > QRS[-1] + int((2.0/3.0 * Rm)) and i < QRS[-1] + Rm:

            dec = (M-np.mean(MM))/1.4
            R = 0 + dec

        MFR = M + F + R
        M_list.append(M)
        F_list.append(F)
        R_list.append(R)
        MFR_list.append(MFR)

        if not QRS and MA3[i] > MFR:
            QRS.append(i)

        elif QRS and i > QRS[-1] + ms200 and MA3[i] > MFR:
            QRS.append(i)
            if len(QRS) > 2:
                RR.append(QRS[-1] - QRS[-2])
                if len(RR) > 5:
                    RR.pop(0)
                Rm = int(np.mean(RR))

    QRS.pop(0)
    QRS = np.array(QRS, dtype='int')
    return QRS



# =============================================================================
# Gamboa (2008)
# =============================================================================
def _ecg_findpeaks_gamboa(signal, sampling_rate=1000, tol=0.002):
    """
    From https://github.com/PIA-Group/BioSPPy/blob/e65da30f6379852ecb98f8e2e0c9b4b5175416c3/biosppy/signals/ecg.py#L834

    - Gamboa, H. (2008). Multi-modal behavioral biometrics based on hci and electrophysiology. PhD ThesisUniversidade.
    """

    # convert to samples
    v_100ms = int(0.1 * sampling_rate)
    v_300ms = int(0.3 * sampling_rate)
    hist, edges = np.histogram(signal, 100, density=True)

    TH = 0.01
    F = np.cumsum(hist)

    v0 = edges[np.nonzero(F > TH)[0][0]]
    v1 = edges[np.nonzero(F < (1 - TH))[0][-1]]

    nrm = max([abs(v0), abs(v1)])
    norm_signal = signal / float(nrm)

    d2 = np.diff(norm_signal, 2)

    b = np.nonzero((np.diff(np.sign(np.diff(-d2)))) == -2)[0] + 2
    b = np.intersect1d(b, np.nonzero(-d2 > tol)[0])

    if len(b) < 3:
        rpeaks = []
    else:
        b = b.astype('float')
        rpeaks = []
        previous = b[0]
        for i in b[1:]:
            if i - previous > v_300ms:
                previous = i
                rpeaks.append(np.argmax(signal[int(i):int(i + v_100ms)]) + i)

    rpeaks = sorted(list(set(rpeaks)))
    rpeaks = np.array(rpeaks, dtype='int')
    return rpeaks







# =============================================================================
# Engzee Modified (2012)
# =============================================================================
def _ecg_findpeaks_engzee(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - C. Zeelenberg, A single scan algorithm for QRS detection and feature extraction, IEEE Comp. in Cardiology, vol. 6, pp. 37-42, 1979
    - A. Lourenco, H. Silva, P. Leite, R. Lourenco and A. Fred, "Real Time Electrocardiogram Segmentation for Finger Based ECG Biometrics", BIOSIGNALS 2012, pp. 49-54, 2012.
    """
    engzee_fake_delay = 0

    diff = np.zeros(len(signal))
    for i in range(4, len(diff)):
        diff[i] = signal[i]-signal[i-4]

    ci = [1, 4, 6, 4, 1]
    low_pass = scipy.signal.lfilter(ci, 1, diff)

    low_pass[:int(0.2 * sampling_rate)] = 0

    ms200 = int(0.2 * sampling_rate)
    ms1200 = int(1.2 * sampling_rate)
    ms160 = int(0.16 * sampling_rate)
    neg_threshold = int(0.01 * sampling_rate)

    M = 0
    M_list = []
    neg_m = []
    MM = []
    M_slope = np.linspace(1.0, 0.6, ms1200-ms200)

    QRS = []
    r_peaks = []

    counter = 0

    thi_list = []
    thi = False
    thf_list = []
    thf = False

    for i in range(len(low_pass)):

        # M
        if i < 5 * sampling_rate:
            M = 0.6 * np.max(low_pass[:i + 1])
            MM.append(M)
            if len(MM) > 5:
                MM.pop(0)

        elif QRS and i < QRS[-1] + ms200:

            newM5 = 0.6 * np.max(low_pass[QRS[-1]:i])

            if newM5 > 1.5 * MM[-1]:
                newM5 = 1.1 * MM[-1]

        elif QRS and i == QRS[-1] + ms200:
            MM.append(newM5)
            if len(MM) > 5:
                MM.pop(0)
            M = np.mean(MM)

        elif QRS and i > QRS[-1] + ms200 and i < QRS[-1] + ms1200:

            M = np.mean(MM) * M_slope[i-(QRS[-1] + ms200)]

        elif QRS and i > QRS[-1] + ms1200:
            M = 0.6 * np.mean(MM)

        M_list.append(M)
        neg_m.append(-M)

        if not QRS and low_pass[i] > M:
            QRS.append(i)
            thi_list.append(i)
            thi = True

        elif QRS and i > QRS[-1] + ms200 and low_pass[i] > M:
            QRS.append(i)
            thi_list.append(i)
            thi = True

        if thi and i < thi_list[-1] + ms160:
            if low_pass[i] < -M and low_pass[i-1] > -M:
                # thf_list.append(i)
                thf = True

            if thf and low_pass[i] < -M:
                thf_list.append(i)
                counter += 1

            elif low_pass[i] > -M and thf:
                counter = 0
                thi = False
                thf = False

        elif thi and i > thi_list[-1] + ms160:
            counter = 0
            thi = False
            thf = False

        if counter > neg_threshold:
            unfiltered_section = signal[thi_list[-1] - int(0.01 * sampling_rate):i]
            r_peaks.append(engzee_fake_delay + np.argmax(unfiltered_section) + thi_list[-1] - int(0.01 * sampling_rate))
            counter = 0
            thi = False
            thf = False

    r_peaks = np.array(r_peaks, dtype='int')
    return r_peaks




# =============================================================================
# Stationary Wavelet Transform  (SWT) - Kalidas and Tamil (2017)
# =============================================================================
def _ecg_findpeaks_kalidas(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - Vignesh Kalidas and Lakshman Tamil (2017). Real-time QRS detector using Stationary Wavelet Transform for Automated ECG Analysis. In: 2017 IEEE 17th International Conference on Bioinformatics and Bioengineering (BIBE). Uses the Pan and Tompkins thresolding.
    """
    # Try loading pywt
    try:
        import pywt
    except ImportError:
        raise ImportError("NeuroKit error: ecg_findpeaks(): the 'PyWavelets' "
                          "module is required for this method to run. ",
                          "Please install it first (`pip install PyWavelets`).")

    swt_level = 3
    padding = -1
    for i in range(1000):
        if (len(signal) + i) % 2 ** swt_level == 0:
            padding = i
            break

    if padding > 0:
        signal = np.pad(signal, (0, padding), 'edge')
    elif padding == -1:
        print("Padding greater than 1000 required\n")

    swt_ecg = pywt.swt(signal, 'db3', level=swt_level)
    swt_ecg = np.array(swt_ecg)
    swt_ecg = swt_ecg[0, 1, :]

    squared = swt_ecg * swt_ecg

    f1 = 0.01/sampling_rate
    f2 = 10/sampling_rate

    b, a = scipy.signal.butter(3, [f1 * 2, f2 * 2], btype='bandpass')
    filtered_squared = scipy.signal.lfilter(b, a, squared)

    filt_peaks = _ecg_findpeaks_peakdetect(filtered_squared, sampling_rate)

    filt_peaks = np.array(filt_peaks, dtype='int')
    return filt_peaks





# =============================================================================
# Elgendi et al. (2010)
# =============================================================================
def _ecg_findpeaks_elgendi(signal, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/

    - Elgendi, Mohamed & Jonkman, Mirjam & De Boer, Friso. (2010). Frequency Bands Effects on QRS Detection. The 3rd International Conference on Bio-inspired Systems and Signal Processing (BIOSIGNALS2010). 428-431.
    """

    window1 = int(0.12 * sampling_rate)
    mwa_qrs = _ecg_findpeaks_MWA(abs(signal), window1)

    window2 = int(0.6 * sampling_rate)
    mwa_beat = _ecg_findpeaks_MWA(abs(signal), window2)

    blocks = np.zeros(len(signal))
    block_height = np.max(signal)

    for i in range(len(mwa_qrs)):
        if mwa_qrs[i] > mwa_beat[i]:
            blocks[i] = block_height
        else:
            blocks[i] = 0

    QRS = []

    for i in range(1, len(blocks)):
        if blocks[i-1] == 0 and blocks[i] == block_height:
            start = i

        elif blocks[i-1] == block_height and blocks[i] == 0:
            end = i-1

            if end-start > int(0.08 * sampling_rate):
                detection = np.argmax(signal[start:end + 1]) + start
                if QRS:
                    if detection-QRS[-1] > int(0.3 * sampling_rate):
                        QRS.append(detection)
                else:
                    QRS.append(detection)

    QRS = np.array(QRS, dtype='int')
    return QRS



# =============================================================================
# Utilities
# =============================================================================

def _ecg_findpeaks_MWA(signal, window_size):
    """
    From https://github.com/berndporr/py-ecg-detectors/
    """
    mwa = np.zeros(len(signal))
    for i in range(len(signal)):
        if i < window_size:
            section = signal[0:i]
        else:
            section = signal[i-window_size:i]

        if i != 0:
            mwa[i] = np.mean(section)
        else:
            mwa[i] = signal[i]

    return mwa






def _ecg_findpeaks_peakdetect(detection, sampling_rate=1000):
    """
    From https://github.com/berndporr/py-ecg-detectors/
    """
    min_distance = int(0.25 * sampling_rate)

    signal_peaks = [0]
    noise_peaks = []

    SPKI = 0.0
    NPKI = 0.0

    threshold_I1 = 0.0
    threshold_I2 = 0.0

    RR_missed = 0
    index = 0
    indexes = []

    missed_peaks = []
    peaks = []

    for i in range(len(detection)):

        if i > 0 and i < len(detection) - 1:
            if detection[i-1] < detection[i] and detection[i + 1] < detection[i]:
                peak = i
                peaks.append(i)

                if detection[peak] > threshold_I1 and (peak - signal_peaks[-1]) > 0.3 * sampling_rate:

                    signal_peaks.append(peak)
                    indexes.append(index)
                    SPKI = 0.125 * detection[signal_peaks[-1]] + 0.875 * SPKI
                    if RR_missed != 0:
                        if signal_peaks[-1] - signal_peaks[-2] > RR_missed:
                            missed_section_peaks = peaks[indexes[-2] + 1:indexes[-1]]
                            missed_section_peaks2 = []
                            for missed_peak in missed_section_peaks:
                                if missed_peak - signal_peaks[-2] > min_distance and signal_peaks[-1] - missed_peak > min_distance and detection[missed_peak] > threshold_I2:
                                    missed_section_peaks2.append(missed_peak)

                            if len(missed_section_peaks2) > 0:
                                missed_peak = missed_section_peaks2[np.argmax(detection[missed_section_peaks2])]
                                missed_peaks.append(missed_peak)
                                signal_peaks.append(signal_peaks[-1])
                                signal_peaks[-2] = missed_peak

                else:
                    noise_peaks.append(peak)
                    NPKI = 0.125 * detection[noise_peaks[-1]] + 0.875 * NPKI

                threshold_I1 = NPKI + 0.25 * (SPKI - NPKI)
                threshold_I2 = 0.5 * threshold_I1

                if len(signal_peaks) > 8:
                    RR = np.diff(signal_peaks[-9:])
                    RR_ave = int(np.mean(RR))
                    RR_missed = int(1.66 * RR_ave)

                index = index + 1

    signal_peaks.pop(0)

    return signal_peaks