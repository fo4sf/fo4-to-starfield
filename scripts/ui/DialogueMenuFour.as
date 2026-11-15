// FAL-865. Our ActionScript. Not decompiled from either game.
// Host fills DialogueList_mc through BSUIDataManager / UIDataShuttleConnector.
// Payload field names are UNREAD: this file does not guess them and is not a compiled movie.
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
        public static const ON_SELECT:String = "DialogueMenu_OnDialogueSelect";
        public static const ON_LIST_VIS:String = "DialogueMenu_OnListVisibilityChange";
        public static const SLOTS:Array = ["fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW"];
        public static const MAP_ROWS:int = 4;
        // PAYLOAD_FIELDS: UNREAD. A PC names-only dump fills this. Do not invent it.
    }
}
