function [qdc,qwct] = ratios_to_flows(qc, Rp, Rs)
%RATIOS_TO_FLOWS Summary of this function goes here
%   Detailed explanation goes here
    qdc = qc * (1-Rp);
    if ~isnan(Rs)
        qwct = qc * (Rp+Rs*(1-Rp));
    else
        qwct = qc*Rp;
    end
end

