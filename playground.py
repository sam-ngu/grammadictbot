from GramAddict.core.device_facade import create_device, get_device_info, Direction, Timeout
from GramAddict.core.resources import ResourceID as resources
from GramAddict.core.resources import ClassName


def main(device):
  app_id = "com.instagram.android"
  device = create_device(None, app_id)
  ResourceID = resources(app_id)

  def scrolled_to_top():
    row_search = device.find(
        resourceId=ResourceID.ROW_SEARCH_EDIT_TEXT,
        className=ClassName.EDIT_TEXT,
    )
    return row_search.exists()

  top = scrolled_to_top()
  print('top is',  top)

  # if top
  # then scroll to the bottom 
  list_view = device.find(
      resourceId=ResourceID.LIST, className=ClassName.LIST_VIEW
  )

  print('dir', Direction.DOWN)
  
  # scroll up offset to fully reveal the search bar if exist
  device.swipe(direction=Direction.DOWN, scale=0.5)
  # check if at top, if yes scroll all the way to bottom, else continue
  if scrolled_to_top():
    list_view.viewV2.fling.toEnd()
  else:
    # resume offset
    device.swipe(direction=Direction.UP, scale=0.5)

  # device.
  list_view.viewV2.fling.toEnd()
  # list_view.scroll(direction=Direction.DOWN)
  # device.View.scroll(direction=Direction.DOWN)


if __name__ == "__main__":
  main()