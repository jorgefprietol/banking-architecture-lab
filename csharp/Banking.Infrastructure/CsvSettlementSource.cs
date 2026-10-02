using System.Globalization;
using System.Text.RegularExpressions;
using Banking.Application;
using Banking.Domain;

namespace Banking.Infrastructure;

// Anti-corruption adapter: provider CSV becomes canonical settlement rows.
public sealed class CsvSettlementSource(string path) : ISettlementSource
{
    public IReadOnlyList<SettlementRow> Read()
    {
        var lines = File.ReadAllLines(path);
        if (lines.Length == 0 || lines[0] != "reference,amount_minor") throw new DomainException("invalid_settlement_header");
        return lines.Skip(1).Where(line => !string.IsNullOrWhiteSpace(line)).Select(line =>
        {
            var fields = line.Split(',');
            if (fields.Length != 2 || string.IsNullOrWhiteSpace(fields[0]) || !Regex.IsMatch(fields[1], "^-?[0-9]+$") ||
                !long.TryParse(fields[1], NumberStyles.AllowLeadingSign, CultureInfo.InvariantCulture, out var minor))
                throw new DomainException("invalid_settlement_row");
            return new SettlementRow(fields[0], minor);
        }).ToArray();
    }
}
