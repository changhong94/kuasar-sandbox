// Read one benchmark registry secret through stdin; caller captures stdout
// directly into its child environment. Never invoke with secrets in argv.
package main

import (
    "crypto/aes"
    "crypto/cipher"
    "crypto/sha256"
    "encoding/hex"
    "encoding/json"
    "fmt"
    "os"
    "strings"
)

func main() {
    var in struct{ Root, Sealed string }
    if err := json.NewDecoder(os.Stdin).Decode(&in); err != nil { panic("invalid input") }
    blob, err := hex.DecodeString(in.Sealed)
    if err != nil || len(blob) < 32 { panic("invalid record") }
    for _, s := range strings.Split(in.Root, ":") {
        key, err := hex.DecodeString(s)
        if err != nil { panic("invalid root") }
        hash := sha256.Sum256(key)
        if string(hash[:4]) != string(blob[:4]) { continue }
        block, err := aes.NewCipher(key)
        if err != nil { panic("invalid key") }
        aead, err := cipher.NewGCM(block)
        if err != nil { panic("invalid cipher") }
        plain, err := aead.Open(nil, blob[4:16], blob[16:], nil)
        if err != nil { panic("authentication failed") }
        fmt.Print(string(plain))
        return
    }
    panic("key not found")
}
