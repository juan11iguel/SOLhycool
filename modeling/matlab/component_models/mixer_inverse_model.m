function Tin_2 = mixer_inverse_model(Qin, Qout, Tin, Tout)
    if Qin - Qout > 1e-3
        throw(MException("mixer_inverse_model:invalid_inputs", "Qin (%.2f) cannot be larger than Qout (%.2f)", Qin, Qout))
    end
    if abs(Qin - Qout) < 1e-3
        Tin_2 = nan; % Could be anything
    else
        Tin_2 = (Tout*Qout - Tin*Qin) / (Qout - Qin);
    end
end
