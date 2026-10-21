using System;
using System.Globalization;
using System.Text.Json;
using cAlgo.API;

namespace cAlgo.Robots
{
    // One-shot metadata collection only. AccessRights.None is not itself a
    // trading prohibition; the absence of trading calls is intentional.
    [Robot(TimeZone = TimeZones.UTC, AccessRights = AccessRights.None)]
    public class ContractSpecExporter : Robot
    {
        [Parameter("Expected broker login", DefaultValue = "")]
        public string ExpectedLogin { get; set; }
        [Parameter("Capture nonce", DefaultValue = "")]
        public string CaptureNonce { get; set; }

        private static string Exact(double value) => value.ToString("R", CultureInfo.InvariantCulture);

        protected override void OnStart()
        {
            try
            {
                if (Account.IsLive || RunningMode != RunningMode.RealTime || SymbolName != "EURUSD"
                    || Account.BrokerName != "FxPro" || Account.Asset.Name != "USD"
                    || Account.Number.ToString(CultureInfo.InvariantCulture) != ExpectedLogin
                    || !System.Text.RegularExpressions.Regex.IsMatch(CaptureNonce ?? "", "\\A[0-9a-f]{32}\\z"))
                {
                    Print("CONTRACT_EXPORT_REFUSED: demo EURUSD/account/nonce mismatch");
                    return;
                }
                var record = new
                {
                    format = 1, source = "ctrader_algo_contract_exporter_v1", nonce = CaptureNonce,
                    observed_at = Server.TimeInUtc.ToString("O", CultureInfo.InvariantCulture),
                    is_live = Account.IsLive, running_mode = RunningMode.ToString(),
                    broker_login = ExpectedLogin, broker = Account.BrokerName, currency = Account.Asset.Name,
                    symbol = SymbolName, tick_size = Exact(Symbol.TickSize), pip_size = Exact(Symbol.PipSize),
                    lot_size = Exact(Symbol.LotSize), minimum = Exact(Symbol.VolumeInUnitsMin),
                    maximum = Exact(Symbol.VolumeInUnitsMax), step = Exact(Symbol.VolumeInUnitsStep)
                };
                Print("CONTRACT_SPEC_JSON:" + JsonSerializer.Serialize(record));
            }
            finally { Stop(); }
        }
    }
}
