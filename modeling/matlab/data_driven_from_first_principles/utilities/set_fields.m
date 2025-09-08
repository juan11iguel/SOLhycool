function target = set_fields(target, source)
    fields = fieldnames(source);
    for i = 1:numel(fields)
        target.(fields{i}) = source.(fields{i});
    end
end