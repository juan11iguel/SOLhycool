function [qdc,qwct,qwct_p,qwct_s] = ratios_to_flows(qc, Rp, Rs)
%RATIOS_TO_FLOWS Summary of this function goes here
%   Detailed explanation goes here
    qdc = qc * (1-Rp);
    qwct_p = qc*Rp;

    if ~isnan(Rs)
        qwct_s = qdc * Rs;
    else
        qwct_s = 0;
    end
    qwct = qwct_p + qwct_s;
end

