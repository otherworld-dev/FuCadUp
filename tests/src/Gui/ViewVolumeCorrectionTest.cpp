// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <Inventor/SbViewVolume.h>
#include <Inventor/SbViewportRegion.h>
#include <Inventor/SoDB.h>
#include <Inventor/nodes/SoOrthographicCamera.h>

#include <Gui/Inventor/ViewVolumeCorrection.h>

// mappedViewVolume has to give the volume as it is rendered under ADJUST_CAMERA: a view wider
// than tall shows height * aspect across, a taller one shows the full height's width and
// height / aspect up. Coin 4.0.2 (the system Coin on Ubuntu) reads the aspect ratio from the
// result viewport before assigning it, so whatever that argument held on the way in decided
// the answer; the bundled Coin reads the input viewport. Both must agree here.

class ViewVolumeCorrectionTest: public ::testing::Test
{
protected:
    static void SetUpTestSuite()
    {
        if (!SoDB::isInitialized()) {
            SoDB::init();
        }
    }

    void SetUp() override
    {
        camera = new SoOrthographicCamera;
        camera->ref();
        camera->height = cameraHeight;
        camera->aspectRatio = 1.0F;
        camera->viewportMapping = SoCamera::ADJUST_CAMERA;
    }

    void TearDown() override
    {
        camera->unref();
    }

    static constexpr float cameraHeight = 10.0F;
    SoOrthographicCamera* camera {nullptr};
};

TEST_F(ViewVolumeCorrectionTest, wideViewIsWiderByItsAspect)
{
    const SbViewportRegion viewport(1400, 478);
    const float aspect = 1400.0F / 478.0F;

    const Gui::MappedView mapped = Gui::mappedViewVolume(*camera, viewport);

    EXPECT_NEAR(mapped.volume.getWidth(), cameraHeight * aspect, 1e-3F);
    EXPECT_NEAR(mapped.volume.getHeight(), cameraHeight, 1e-3F);
    EXPECT_EQ(mapped.viewport.getViewportSizePixels(), SbVec2s(1400, 478));
}

TEST_F(ViewVolumeCorrectionTest, tallViewIsTallerByItsAspect)
{
    const SbViewportRegion viewport(700, 1078);
    const float aspect = 700.0F / 1078.0F;

    const Gui::MappedView mapped = Gui::mappedViewVolume(*camera, viewport);

    EXPECT_NEAR(mapped.volume.getWidth(), cameraHeight, 1e-3F);
    EXPECT_NEAR(mapped.volume.getHeight(), cameraHeight / aspect, 1e-3F);
    EXPECT_EQ(mapped.viewport.getViewportSizePixels(), SbVec2s(700, 1078));
}
