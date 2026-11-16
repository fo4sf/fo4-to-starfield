// FAL-865. Our ActionScript. Not decompiled. Not a compiled movie. Not DialogueMenu.
// Binds fo4sfOptN/E/S/W on this unnamed container (not on sealed DialogueMenu).
// Subscribe DialogueListData; fill aChoices[0..3].sChoiceText; select selectedIndex = uEntryID.
package
{
    import flash.display.DisplayObject;
    import flash.display.DisplayObjectContainer;
    import flash.display.MovieClip;
    import flash.events.Event;
    import flash.events.MouseEvent;
    import flash.text.TextField;
    import flash.text.TextFieldAutoSize;
    import flash.text.TextFormat;
    import flash.utils.getDefinitionByName;

    public dynamic class Fo4sfDialogueSlots extends MovieClip
    {
        public static const SHUTTLE_MANAGER:String = "BSUIDataManager";
        public static const LIST_PROVIDER:String = "DialogueListData";
        public static const CHOICES:String = "aChoices";
        public static const CHOICE_TEXT:String = "sChoiceText";
        public static const ENTRY_ID:String = "uEntryID";
        public static const ON_SELECT:String = "DialogueMenu_OnDialogueSelect";
        public static const SELECT_KEY:String = "selectedIndex";
        public static const SLOTS:Array = ["fo4sfOptN", "fo4sfOptE", "fo4sfOptS", "fo4sfOptW"];
        public static const MAP_ROWS:int = 4;
        public static const HOST_LIST:String = "DialogueList_mc";

        public var lastChoices:Array;

        public function Fo4sfDialogueSlots()
        {
            lastChoices = [];
            addEventListener(Event.ADDED_TO_STAGE, onAdded);
        }

        public function onAdded(e:Event):void
        {
            hideHostList();
            var mgr:Object = shuttle();
            if (mgr != null)
            {
                mgr.Subscribe(LIST_PROVIDER, onChoiceListUpdate);
            }
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                var clip:DisplayObject = this.getChildByName(SLOTS[i]);
                if (clip != null)
                {
                    clip.addEventListener(MouseEvent.CLICK, onSlotClick);
                }
                i++;
            }
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
            var mgr:Object = shuttle();
            if (mgr == null)
            {
                return;
            }
            mgr.Dispatch(ON_SELECT, payload);
        }

        public function hideHostList():void
        {
            var p:DisplayObjectContainer = this.parent;
            if (p == null)
            {
                return;
            }
            var list:DisplayObject = p.getChildByName(HOST_LIST);
            if (list != null)
            {
                list.visible = false;
            }
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
                var tf:TextField = new TextField();
                tf.autoSize = TextFieldAutoSize.LEFT;
                tf.multiline = true;
                tf.wordWrap = true;
                tf.width = 420;
                tf.defaultTextFormat = new TextFormat("_sans", 22, 0x1AFF80);
                tf.text = value;
                box.addChild(tf);
            }
        }

        private function onSlotClick(e:MouseEvent):void
        {
            var i:int = 0;
            while (i < MAP_ROWS)
            {
                if (e.currentTarget != null && e.currentTarget.name == SLOTS[i])
                {
                    selectSlot(i);
                    return;
                }
                i++;
            }
        }

        private function shuttle():Object
        {
            try
            {
                return getDefinitionByName(SHUTTLE_MANAGER);
            }
            catch (err:Error)
            {
                return null;
            }
            return null;
        }
    }
}
