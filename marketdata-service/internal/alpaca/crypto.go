package alpaca

import "strings"

// knownCryptoSymbols is the set of crypto base symbols we support.
var knownCryptoSymbols = map[string]bool{
	"BTC":   true,
	"ETH":   true,
	"SOL":   true,
	"DOGE":  true,
	"AVAX":  true,
	"LINK":  true,
	"DOT":   true,
	"MATIC": true,
	"LTC":   true,
	"UNI":   true,
	"SHIB":  true,
	"ADA":   true,
}

// IsCrypto returns true if the symbol is a known cryptocurrency.
// Handles both "BTC" and "BTC/USD" formats.
func IsCrypto(symbol string) bool {
	base := strings.Split(symbol, "/")[0]
	return knownCryptoSymbols[strings.ToUpper(base)]
}

// CryptoAlpacaSymbol converts a base crypto symbol to the Alpaca pair format.
// "BTC" -> "BTC/USD", "ETH" -> "ETH/USD".
// If already in pair format, returns as-is.
func CryptoAlpacaSymbol(symbol string) string {
	if strings.Contains(symbol, "/") {
		return strings.ToUpper(symbol)
	}
	return strings.ToUpper(symbol) + "/USD"
}
