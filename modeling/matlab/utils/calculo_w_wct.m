function error = calculo_w_wct(w_fan, Tout_ref, Tamb, q, Tin, HR, tm)
    % Evaluates fan % for WASCOP WCT cooler 
    % - Inputs
    %   - $Tout_{ref}$  $[\degree C]$ Temperature setpoint
    %   - $T_{amb}$  $[\degree C]$ Ambient temperature (Dry bulb)
    %   - $T_{in}$  $[\degree C]$ Inlet temperature to dry cooling system
    %   - $q$  $[m3/h]$ Volumetric flow of fluid to cool
    %   - $w_fan$ $[%]$ Fan load (0-100 -> 0-max_freq Hz) 
    %   - $tm$ Model type (data -> 1, physic -> 2) 
    % - Outputs
    %   - $error$  $[\degree C]$ Temperature difference     

if tm==1
    [Tout, Pe_wct, Mw_lost] = wct_model(Tamb, HR, Tin, q, w_fan);  
else
    [Tout, Mw_lost_Lmin]=wct_model_elx(Tamb, HR, Tin, q, w_fan, 50,'c_poppe',1.52,'n_poppe',-0.69);
end;
    
error = abs(Tout_ref - Tout);
