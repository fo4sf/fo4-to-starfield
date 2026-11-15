// FAL-865. Our ActionScript. Not decompiled from either game. Not a compiled movie.
// PC PASS §1b: Subscribe(DialogueListData, onChoiceListUpdate).
// Bind four slots to aChoices[0..3].sChoiceText.
// On select send DialogueMenu_OnDialogueSelect { selectedIndex: uEntryID }.
package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.MovieClip;
    import flash.text.TextField;

    public class DialogueMenuFour extends MovieClip
    {
        public static const KEEP_MENU:String = "DialogueMenu";
        public static const HOST_ROOT:String = "Menu_mc";
        public static const HOST_LIST:String = "DialogueList_mc";
        public static const HOST_LIST_ENTRY:String = "DialogueScrollingListEntry";
        public static const SHUTTLE_MANAGER:String = "BSUIDataManager";
        public static const SHUTTLE_CONNECTOR:String = "UIDataShuttleConnector";
        public static const SUBSCRIBE:String = "Subscribe";
        public static const DISPATCH:String = "Dispatch";
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

        public var lastChoices:Array;

        public function DialogueMenuFour()
        {
            lastChoices = [];
            BSUIDataManager.Subscribe(LIST_PROVIDER, onChoiceListUpdate);
        }

        public function onChoiceListUpdate(data:Object):void
        {
            var src:Object = data;
            if (data != null && data.data != null && data.aChoices == null)
            {
                src = data.data;
            }
            lastChoices = (src != null && src.aChoices is Array) ? (src.aChoices as Array) : [];
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                var row:Object = (i < lastChoices.length) ? lastChoices[i] : null;
                var text:String = (row != null && row.sChoiceText != null) ? String(row.sChoiceText) : "";
                fillSlot(SLOTS[i], text);
                i++;
            }
        }

        public function selectSlot(i:int):void
        {
            if (lastChoices == null || i < 0 || i >= MAP_ROWS || i >= lastChoices.length)
            {
                return;
            }
            var row:Object = lastChoices[i];
            if (row == null || row[ENTRY_ID] == null)
            {
                return;
            }
            var payload:Object = {};
            payload[SELECT_KEY] = row[ENTRY_ID];
            sendSelect(ON_SELECT, payload);
        }

        public function fillSlot(name:String, text:String):void
        {
            var value:String = (text == null) ? "" : text;
            var clip:DisplayObject = this.getChildByName(name);
            if (clip == null)
            {
                return;
            }
            if (clip is TextField)
            {
                (clip as TextField).text = value;
                return;
            }
            if (clip is DisplayObjectContainer)
            {
                var box:DisplayObjectContainer = clip as DisplayObjectContainer;
                var i:int = 0;
                while (i < box.numChildren)
                {
                    var child:DisplayObject = box.getChildAt(i);
                    if (child is TextField)
                    {
                        (child as TextField).text = value;
                        return;
                    }
                    i++;
                }
            }
        }

        public function sendSelect(eventName:String, payload:Object):void
        {
            if (eventName != ON_SELECT || payload == null || payload[SELECT_KEY] == null)
            {
                return;
            }
            BSUIDataManager.Dispatch(eventName, payload);
        }
    }
}
