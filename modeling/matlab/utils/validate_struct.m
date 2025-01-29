function validate_struct(inputStruct, refStruct)
    % Get field names of both structures
    inputFields = fieldnames(inputStruct);
    refFields = fieldnames(refStruct);

    % Check if field names match
    if ~isequal(sort(inputFields), sort(refFields))
        error('The input structure must have the same fields as the reference structure.');
    end

    % Check if types match for each field
    for i = 1:numel(refFields)
        fieldName = refFields{i};
        if ~isempty(inputStruct) && ~isempty(refStruct) && ...
                ~isa(inputStruct.(fieldName), class(refStruct.(fieldName)))
            error('Field "%s" has the wrong type. Expected "%s", got "%s".', ...
                fieldName, class(refStruct.(fieldName)), class(inputStruct.(fieldName)));
        end
    end
end