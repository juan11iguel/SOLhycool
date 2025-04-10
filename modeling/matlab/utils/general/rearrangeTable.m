function rearrangedTable = rearrangeTable(referenceTable, inputTable)
    % REARRANGETABLE Rearranges the columns of inputTable to match referenceTable.
    % Missing columns in inputTable are filled with NaN.
    % Excess columns in inputTable are appended at the end.

    % Get the column names from the reference and input tables
    referenceColumns = referenceTable.Properties.VariableNames;
    inputColumns = inputTable.Properties.VariableNames;

    % Identify common, missing, and excess columns
    commonColumns = intersect(referenceColumns, inputColumns, 'stable');
    missingColumns = setdiff(referenceColumns, inputColumns, 'stable');
    excessColumns = setdiff(inputColumns, referenceColumns, 'stable');

    % Extract common columns from the input table
    rearrangedTable = inputTable(:, commonColumns);

    % Add missing columns, filled with NaN
    for i = 1:numel(missingColumns)
        rearrangedTable.(missingColumns{i}) = NaN(height(rearrangedTable), 1);
    end

    % Append excess columns from the input table
    if ~isempty(excessColumns)
        excessTable = inputTable(:, excessColumns);
        rearrangedTable = [rearrangedTable, excessTable];
    end

    % Reorder columns to match the reference table, followed by excess columns
    rearrangedTable = rearrangedTable(:, [referenceColumns, excessColumns]);
end

