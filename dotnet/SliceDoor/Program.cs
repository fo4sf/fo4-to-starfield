// SliceDoor: the playable slice's working door between the converted Commonwealth terrain and the converted Red Rocket
// cave (docs/slice/redrocket-door.md). Claude's tool; nothing here is deployed.
//
//   dotnet run -- fo4 <Fallout4.esm> <out.json> [interior door hex] [exterior door hex]
//        the two Fallout 4 ends of the load-door link (default 05E844 in RedRocket01, 08EB65 in Commonwealth), their base
//   dotnet run -- sf-door <Starfield.esm> <out.json> [DOOR hex]
//        the vanilla automatic cave load door AutoloadDoor_Cave (24F9CE): record, references, where overlay worlds keep XTELs
//   dotnet run -- port <FO4Port.esm> <cell EditorID> <out.json> [x y z radius]
//        the converted interior as the pinned build holds it: XTEL / DOOR references, references near a point
//   dotnet run -- build <params.json> <Starfield.esm> <FO4TerrainExp2.esm> <FO4Port.esm> <out dir>
//        writes the link plugin (params from scripts/slice/make_redrocket_door.py stage)
//   dotnet run -- check <plugin> <Starfield.esm> <FO4TerrainExp2.esm> <FO4Port.esm> <params.json> <out.json>
//        reads the link plugin back with its masters and checks every link, both XTELs and the override copies
if (args.Length < 2)
{
    Console.Error.WriteLine("usage: SliceDoor fo4|sf-door|port|build|check ... (see Program.cs)");
    return 2;
}
return args[0] switch
{
    "fo4" => Inspect.Fallout4Source(args),
    "sf-door" => Inspect.SfDoor(args),
    "port" => Inspect.Port(args),
    "build" => Build.Run(args),
    "check" => Check.Run(args),
    _ => 2,
};
