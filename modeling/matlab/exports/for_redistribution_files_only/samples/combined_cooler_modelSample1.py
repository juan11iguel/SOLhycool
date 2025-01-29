#!/usr/bin/env python
"""
Sample script that uses the combined_cooler_model module created using
MATLAB Compiler SDK.

Refer to the MATLAB Compiler SDK documentation for more information.
"""

import combined_cooler_model
# Import the matlab module only after you have imported
# MATLAB Compiler SDK generated Python modules.
import matlab

my_combined_cooler_model = combined_cooler_model.initialize()

Tamb_CIn = matlab.double([20.9233329223592], size=(1, 1))
HR_ppIn = matlab.double([42.056076841053], size=(1, 1))
mv_kghIn = matlab.double([303.464303911118], size=(1, 1))
qc_m3hIn = matlab.double([17.9985515828058], size=(1, 1))
RpIn = matlab.double([0.346], size=(1, 1))
RsIn = matlab.double([0.0], size=(1, 1))
wdcIn = matlab.double([59.5066639786738], size=(1, 1))
wwctIn = matlab.double([24.6752370543154], size=(1, 1))
TvIn = matlab.double([43.3244585138288], size=(1, 1))
Ce_kWeOut, Cw_lhOut, detailedOut = my_combined_cooler_model.combined_cooler_model(Tamb_CIn, HR_ppIn, mv_kghIn, qc_m3hIn, RpIn, RsIn, wdcIn, wwctIn, TvIn, nargout=3)
print(Ce_kWeOut, Cw_lhOut, detailedOut, sep='\n')

my_combined_cooler_model.terminate()
