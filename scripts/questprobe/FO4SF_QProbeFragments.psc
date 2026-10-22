Scriptname FO4SF_QProbeFragments extends Quest Hidden Const
{The stage fragment script of FO4SF_QProbe (docs/questprobe/engine-questions.md, E1), laid out as Starfield's own
 QF_ fragment scripts are: one function per stage log entry, named as the plugin's VMAD fragment names it.}

Function Fragment_Stage_0010_Item_00()
    ((self as Quest) as FO4SF_QProbeQuest).FragmentRan(10)
EndFunction
