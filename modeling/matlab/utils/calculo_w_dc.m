function error = calculo_w_dc(w_fan, Tout_ref, Tamb, q, Tin, tm)
    % Evaluates fan % for WASCOP DC cooler 
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
    Tout = dc_model(Tamb, Tin, q, w_fan);
else
    Tout = ache_model(Tamb, w_fan, Tin, q);
end;
    
error = abs(Tout_ref - Tout);