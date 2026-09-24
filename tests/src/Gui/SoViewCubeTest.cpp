// SPDX-License-Identifier: LGPL-2.1-or-later

#include <gtest/gtest.h>

#include <numbers>

#include <Inventor/SbRotation.h>
#include <Inventor/SbVec2s.h>
#include <Inventor/SoDB.h>
#include <Inventor/SoType.h>

#include <Gui/Inventor/SoViewCube.h>

using Gui::SoViewCube;
using PickId = Gui::SoNaviCube::PickId;

namespace
{
constexpr short viewportSize = 200;
constexpr float pi = std::numbers::pi_v<float>;

SbRotation frontView()
{
    return SbRotation(SbVec3f(1.0F, 0.0F, 0.0F), pi / 2.0F);
}

SbRotation isoView()
{
    return SbRotation(SbVec3f(0.0F, 0.0F, 1.0F), SbVec3f(1.0F, -1.0F, 1.0F));
}

/// The viewer pixel under an overlay point given as 0..1 with y down.
SbVec2s at(float x, float yDown)
{
    return SbVec2s(
        static_cast<short>(x * viewportSize),
        static_cast<short>((1.0F - yDown) * viewportSize)
    );
}

class SoViewCubeTest: public ::testing::Test
{
protected:
    static void SetUpTestSuite()
    {
        if (!SoDB::isInitialized()) {
            SoDB::init();
        }
        if (SoViewCube::getClassTypeId() == SoType::badType()) {
            SoViewCube::initClass();
        }
    }

    void SetUp() override
    {
        cube = new SoViewCube;
        cube->ref();
        cube->viewportRect.setValue(0.0F, 0.0F, viewportSize, viewportSize);
        cube->cameraIsOrthographic = TRUE;
    }

    void TearDown() override
    {
        cube->unref();
    }

    SoViewCube* cube {nullptr};
};
}  // namespace

TEST_F(SoViewCubeTest, theCentreOfTheFacingFaceIsThatFace)
{
    cube->cameraOrientation = SbRotation();
    EXPECT_EQ(cube->pickAt(at(0.5F, 0.5F)), PickId::Top);
    cube->cameraOrientation = frontView();
    EXPECT_EQ(cube->pickAt(at(0.5F, 0.5F)), PickId::Front);
}

TEST_F(SoViewCubeTest, theBandsOfTheFacingFaceAreItsEdgesAndCorners)
{
    // Face-on the face spans 0.262..0.738 of the overlay; its bands are the outer 0.105.
    cube->cameraOrientation = frontView();
    EXPECT_EQ(cube->pickAt(at(0.5F, 0.31F)), PickId::FrontTop);
    EXPECT_EQ(cube->pickAt(at(0.69F, 0.5F)), PickId::FrontRight);
    EXPECT_EQ(cube->pickAt(at(0.69F, 0.31F)), PickId::FrontTopRight);
    EXPECT_EQ(cube->pickAt(at(0.31F, 0.69F)), PickId::FrontBottomLeft);
}

TEST_F(SoViewCubeTest, outsideTheCubeIsNothing)
{
    cube->cameraOrientation = frontView();
    EXPECT_EQ(cube->pickAt(at(0.2F, 0.5F)), PickId::None);
    EXPECT_EQ(cube->pickAt(SbVec2s(viewportSize + 10, 10)), PickId::None);
}

TEST_F(SoViewCubeTest, controlsAnswerOnlyWhileLive)
{
    cube->cameraOrientation = frontView();
    cube->controlsLive = FALSE;
    EXPECT_EQ(cube->pickAt(at(0.09F, 0.09F)), PickId::None);
    cube->controlsLive = TRUE;
    EXPECT_EQ(cube->pickAt(at(0.09F, 0.09F)), PickId::Home);
    EXPECT_EQ(cube->pickAt(at(0.5F, 0.15F)), PickId::ArrowNorth);
}

TEST_F(SoViewCubeTest, trianglesAreNotThereWhenTheViewIsNotFaceOn)
{
    cube->cameraOrientation = isoView();
    cube->controlsLive = TRUE;
    EXPECT_NE(cube->pickAt(at(0.5F, 0.15F)), PickId::ArrowNorth);
}

TEST_F(SoViewCubeTest, theHighlightLightsTheTilesOfAnEdge)
{
    cube->cameraOrientation = frontView();
    cube->hiliteId = static_cast<int>(PickId::FrontTop);
    EXPECT_EQ(cube->hilitedTileCount(), 2);
    cube->hiliteId = static_cast<int>(PickId::FrontTopRight);
    EXPECT_EQ(cube->hilitedTileCount(), 3);
    cube->hiliteId = static_cast<int>(PickId::Home);
    EXPECT_EQ(cube->hilitedTileCount(), 0);
}
