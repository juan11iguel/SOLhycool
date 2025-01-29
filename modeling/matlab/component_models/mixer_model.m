function [Qout, Tout] = mixer_model(Qin_1, Qin_2, Tin_1, Tin_2)

    %MIXER Summary of this function goes here
    %   Detailed explanation goes here
    if Qin_1 < 1e-6
        Qout = Qin_2;
        Tout = Tin_2;
    elseif Qin_2 < 1e-6
        Qout = Qin_1;
        Tout = Tin_1;
    else
        Qout = Qin_1 + Qin_2;
        Tout = Tin_1 * Qin_1/Qout + Tin_2 * Qin_2/Qout;
    end
end