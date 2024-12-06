function [Qout, Tout] = mixer_model(Qin_1, Qin_2, Tin_1, Tin_2)

    %MIXER Summary of this function goes here
    %   Detailed explanation goes here
    
    Qout = Qin_1 + Qin_2;
    Tout = Tin_1 * Qin_1/Qout + Tin_2 * Qin_2/Qout;
    
end

