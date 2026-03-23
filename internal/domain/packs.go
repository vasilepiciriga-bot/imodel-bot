package domain

type Pack struct{ Key string; Credits int; Stars int }

var Packs = []Pack{
    {Key: "pack10", Credits: 10, Stars: 200},
    {Key: "pack30", Credits: 30, Stars: 500},
    {Key: "pack100", Credits: 100, Stars: 1200},
}

func FindPack(key string) *Pack {
    for i := range Packs { if Packs[i].Key == key { return &Packs[i] } }
    return nil
}
