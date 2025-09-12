addpath("../component_models/")

Qc_nominal = 90*10^3; % kWth
Tv_nominal = 41.5; % ºC
dc_ratio = 0.75; % 0.25 0.5 0.75

%% Scale surface condenser
[n_tb_sc_scaled, A_scaled] = scale_sc(Qc_nominal, Tv_nominal)

% Test scaled model
[Tc_in, Tc_out] = condenser_model(mv_kgs=nan, Tv_C=Tv_nominal, mc_kgs=nan, A=A_scaled, n_tb=n_tb_sc_scaled, option=3)

%% Scale Air-Cooled Heat Exchanger
[n_dc] = scale_dc(Qc_nominal*dc_ratio)

% Test the scaled model
% [Tout, Ce] = dc_model_physical(Tamb, Tin, q, w_fan, n_dc);

%% Scale wet cooling tower
% Done ad-hoc for andasol, no function is implemented to return the scaled
% parameters automatically