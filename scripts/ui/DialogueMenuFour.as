// FAL-865. Our ActionScript. Not decompiled from either game. Not a compiled movie.
// PC PASS §1b (file read): bind four slots to DialogueListData.aChoices[0..3].sChoiceText.
// On select send DialogueMenu_OnDialogueSelect { selectedIndex: uEntryID }.
package
{
    public class DialogueMenuFour
    {
        public static const KEEP_MENU:String = "DialogueMenu";
        public static const HOST_ROOT:String = "Menu_mc";
        public static const HOST_LIST:String = "DialogueList_mc";
        public static const HOST_LIST_ENTRY:String = "DialogueScrollingListEntry";
        public static const SHUTTLE_MANAGER:String = "BSUIDataManager";
        public static const SHUTTLE_CONNECTOR:String = "UIDataShuttleConnector";
        public static const SUBSCRIBE:String = "Subscribe";
        public static const LIST_PROVIDER:String = "DialogueListData";
        public static const CHOICES:String = "aChoices";
        public static const CHOICE_TEXT:String = "sChoiceText";
        public static const CAN_CHOOSE:String = "bCanBeChosen";
        public static const ALREADY_SAID:String = "bWasAlreadySaid";
        public static const ENTRY_ID:String = "uEntryID";
        public static const ON_SELECT:String = "DialogueMenu_OnDialogueSelect";
        public static const SELECT_KEY:String = "selectedIndex";
        public static const ON_LIST_VIS:String = "DialogueMenu_OnListVisibilityChange";
        public static const LIST_VIS_KEY:String = "isVisible";
        public static const SLOTS:Array = ["fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW"];
        public static const MAP_ROWS:int = 4;
    }
}
