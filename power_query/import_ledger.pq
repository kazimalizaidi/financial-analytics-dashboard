// Power Query (M) template: loads a ledger CSV in the same shape as the Transactions table.
// Setup: Data > Get Data > From Other Sources > Blank Query > Advanced Editor, paste this in,
// change the file path, then Close & Load To... a table on a new sheet.
let
    Source   = Csv.Document(File.Contents("C:\path\to\helmquant_ledger.csv"), [Delimiter=",", Encoding=65001, QuoteStyle=QuoteStyle.Csv]),
    Promoted = Table.PromoteHeaders(Source, [PromoteAllScalars=true]),
    Typed    = Table.TransformColumnTypes(Promoted, {
                 {"Date", type date}, {"Description", type text}, {"Category", type text},
                 {"Type", type text}, {"Account", type text}, {"Amount", type number},
                 {"Status", type text}, {"Source", type text}}),
    Clean    = Table.SelectRows(Typed, each [Date] <> null and [Amount] <> null and [Amount] > 0),
    Sorted   = Table.Sort(Clean, {{"Date", Order.Ascending}})   // the dashboard needs the ledger oldest first
in
    Sorted
